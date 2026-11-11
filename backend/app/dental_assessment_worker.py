import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import and_, or_, select

from app.database import SessionLocal
from app.models import (
    AIAnalysisPrediction,
    AIAnalysisResult,
    DentalAssessmentJob,
    DentalImage,
)
from app.services.dental_image_service import UPLOAD_DIRECTORY
from app.services.dental_result_metrics import (
    extract_segmentation_metrics,
)


logger = logging.getLogger(__name__)

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
PROJECT_DIRECTORY = BACKEND_DIRECTORY.parent

RUNNER = (
    PROJECT_DIRECTORY
    / "ai"
    / "image processing"
    / "assessment_runner.py"
)

RESULT_DIRECTORY = (
    BACKEND_DIRECTORY
    / "private_uploads"
    / "dental_assessments"
)

CONDITIONS = ("healthy", "plaque", "gingivitis", "calculus")
MODEL_VERSION = "dental-pipeline-v2-mobilenet-seg"

PROCESS_TIMEOUT = 240
LEASE_SECONDS = 360
MAX_ATTEMPTS = 2


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def claim_job():
    with SessionLocal() as db:
        now = utc_now()

        job = db.scalar(
            select(DentalAssessmentJob)
            .where(
                or_(
                    DentalAssessmentJob.status == "queued",
                    and_(
                        DentalAssessmentJob.status == "running",
                        DentalAssessmentJob.locked_until < now,
                    ),
                )
            )
            .order_by(DentalAssessmentJob.assessment_job_id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        if job is None:
            return None

        if job.attempts >= MAX_ATTEMPTS:
            job.status = "failed"
            job.error_message = (
                "Processing could not be completed. "
                "Please upload the photo again."
            )
            job.finished_at = now
            job.locked_until = None
            db.commit()
            return None

        token = str(uuid4())

        job.status = "running"
        job.attempts += 1
        job.claim_token = token
        job.started_at = now
        job.finished_at = None
        job.error_message = None
        job.locked_until = now + timedelta(seconds=LEASE_SECONDS)

        claimed = (
            job.assessment_job_id,
            job.dental_image_id,
            token,
        )

        db.commit()
        return claimed


def lock_claim(db, job_id, token):
    return db.scalar(
        select(DentalAssessmentJob)
        .where(
            DentalAssessmentJob.assessment_job_id == job_id,
            DentalAssessmentJob.status == "running",
            DentalAssessmentJob.claim_token == token,
        )
        .with_for_update()
    )


def finish_without_result(job_id, token, status, message):
    with SessionLocal() as db:
        job = lock_claim(db, job_id, token)

        if job is None:
            return

        job.status = status
        job.error_message = message
        job.finished_at = utc_now()
        job.locked_until = None

        db.commit()


def uploaded_image_path(image_id):
    with SessionLocal() as db:
        image = db.get(DentalImage, image_id)

        if image is None:
            raise ValueError("Uploaded image record is missing.")

        filename = image.image_url

    if not re.fullmatch(r"[0-9a-f]{32}\.jpg", filename):
        raise ValueError("Invalid uploaded image filename.")

    directory = UPLOAD_DIRECTORY.resolve()
    target = (directory / filename).resolve()

    if target.parent != directory or not target.is_file():
        raise ValueError("Uploaded image file is missing.")

    return target


def run_models(image_path, output_directory, stop_event):
    environment = os.environ.copy()
    environment["TF_NUM_INTRAOP_THREADS"] = "2"
    environment["TF_NUM_INTEROP_THREADS"] = "2"
    environment["TF_CPP_MIN_LOG_LEVEL"] = "2"
    environment["MPLBACKEND"] = "Agg"

    command = [
        sys.executable,
        "-B",
        str(RUNNER),
        "--image",
        str(image_path),
        "--output-dir",
        str(output_directory),
    ]

    process = subprocess.Popen(
        command,
        cwd=str(RUNNER.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        creationflags=(
            subprocess.CREATE_NO_WINDOW
            if os.name == "nt"
            else 0
        ),
    )

    deadline = utc_now() + timedelta(seconds=PROCESS_TIMEOUT)

    try:
        while True:
            if stop_event.is_set():
                raise InterruptedError("Worker is stopping.")

            if utc_now() >= deadline:
                raise TimeoutError("Model processing timed out.")

            try:
                stdout, stderr = process.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                continue

        if process.returncode != 0:
            logger.error(
                "Dental model runner failed: %s",
                stderr[-2000:],
            )
            raise RuntimeError("Model runner failed.")

        result = json.loads(stdout)

        if result.get("status") not in {"completed", "rejected"}:
            raise ValueError("Unexpected model runner response.")

        return result

    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


def validate_predictions(result):
    predictions = result.get("predictions")

    if not isinstance(predictions, dict):
        raise ValueError("Prediction results are missing.")

    if set(predictions) != set(CONDITIONS):
        raise ValueError("Unexpected prediction conditions.")

    for condition in CONDITIONS:
        prediction = predictions[condition]
        confidence = prediction.get("confidence")
        threshold = prediction.get("threshold")
        positive = prediction.get("positive")

        for value in (confidence, threshold):
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                raise ValueError("Invalid prediction score.")

        if type(positive) is not bool:
            raise ValueError("Invalid prediction decision.")

        if positive != (confidence >= threshold):
            raise ValueError("Prediction threshold mismatch.")

    return predictions


def copy_artifact(source_path, destination, attempt_directory):
    source = Path(source_path).resolve()
    allowed = attempt_directory.resolve()

    if not source.is_relative_to(allowed) or not source.is_file():
        raise ValueError("Invalid generated image path.")

    shutil.copy2(source, destination)


def save_result(job_id, token, payload, attempt_directory):
    result = payload["result"]
    predictions = validate_predictions(result)

    severity = result.get("severity") or {}

    if severity.get("severity") not in {
        "None", "Mild", "Moderate", "Severe"
    }:
        raise ValueError("Invalid severity result.")

    # Keep generated images in predictable, private locations.
    copy_artifact(
        result["gradcam"]["summary"],
        attempt_directory / "heatmap.png",
        attempt_directory,
    )
    copy_artifact(
        result["segmentation"]["segmentation_output"],
        attempt_directory / "segmentation.png",
        attempt_directory,
    )
    copy_artifact(
        result["analysis_summary"],
        attempt_directory / "summary.png",
        attempt_directory,
    )

    with SessionLocal() as db:
        job = lock_claim(db, job_id, token)

        # A restarted worker may already own a newer claim.
        if job is None:
            return

        analysis = AIAnalysisResult(
            dental_image_id=job.dental_image_id,
            analysis_date=utc_now(),
            model_version=MODEL_VERSION,
            heatmap_url=(
                f"/dental-assessments/{job_id}/media/heatmap"
            ),
            segmentation_url=(
                f"/dental-assessments/{job_id}/media/segmentation"
            ),
        )

        db.add(analysis)
        db.flush()

        public_predictions = []

        for condition in CONDITIONS:
            prediction = predictions[condition]

            db.add(
                AIAnalysisPrediction(
                    analysis_id=analysis.analysis_id,
                    condition_name=condition,
                    confidence_score=Decimal(
                        str(prediction["confidence"])
                    ).quantize(Decimal("0.00001")),
                    predicted_positive=prediction["positive"],
                    supported=True,
                )
            )

            public_predictions.append({
                "condition": condition,
                "confidence": prediction["confidence"],
                "threshold": prediction["threshold"],
                "positive": prediction["positive"],
            })

        job.analysis_id = analysis.analysis_id
        job.status = "completed"
        job.finished_at = utc_now()
        job.locked_until = None
        job.error_message = None

        # Only public result fields are returned to the app.
        # Do not store local filesystem paths in this response.
        job.result_summary = {
            "model_version": MODEL_VERSION,
            "predictions": public_predictions,
            "segmentation": extract_segmentation_metrics(
                result.get("segmentation")
            ),
            "severity": {
                "label": severity["severity"],
                "method": "experimental_rule_based",
                "reason": severity.get("reason"),
            },
            "interpretation": (
                "AI screening results for veterinary review. "
                "This is not a confirmed diagnosis."
            ),
            "media": {
                "heatmap": (
                    f"/dental-assessments/{job_id}/media/heatmap"
                ),
                "segmentation": (
                    f"/dental-assessments/{job_id}/media/segmentation"
                ),
                "summary": (
                    f"/dental-assessments/{job_id}/media/summary"
                ),
            },
        }

        db.commit()


def process_job(claimed, stop_event):
    job_id, image_id, token = claimed

    attempt_directory = (
        RESULT_DIRECTORY
        / str(job_id)
        / token
    )

    try:
        image_path = uploaded_image_path(image_id)

        attempt_directory.mkdir(parents=True, exist_ok=False)

        payload = run_models(
            image_path,
            attempt_directory,
            stop_event,
        )

        if payload["status"] == "rejected":
            message = payload.get("message")

            if not isinstance(message, str) or not message.strip():
                message = (
                    "The photo did not pass validation. "
                    "Take a clearer photo of your pet's teeth and gums."
                )

            finish_without_result(
                job_id,
                token,
                "rejected",
                message.strip()[:500],
            )
            return

        save_result(
            job_id,
            token,
            payload,
            attempt_directory,
        )

    except InterruptedError:
        with SessionLocal() as db:
            job = lock_claim(db, job_id, token)

            if job is not None:
                job.status = "queued"
                job.locked_until = None
                db.commit()

    except Exception:
        logger.exception(
            "Dental assessment job %s failed",
            job_id,
        )

        finish_without_result(
            job_id,
            token,
            "failed",
            "The assessment could not be completed. "
            "Please try another photo.",
        )


def run_worker(stop_event):
    while not stop_event.is_set():
        try:
            claimed = claim_job()

            if claimed is not None:
                process_job(claimed, stop_event)
                continue

        except Exception:
            logger.exception("Dental assessment worker failed")

        stop_event.wait(3)