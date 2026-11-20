import json
import logging
import math
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from threading import local
from app.services.model_process_client import ModelProcessClient

from sqlalchemy import and_, or_, select
from app.services.notification_service import notify_assessment_finished

from app.database import SessionLocal
from app.models import (
    AIAnalysisPrediction,
    AIAnalysisResult,
    DentalAssessmentJob,
    DentalImage,
    Pet,
)
from app.services.dental_image_service import UPLOAD_DIRECTORY
from app.services.dental_result_metrics import (
    extract_segmentation_metrics,
)
from app.services.assessment_interpretation import (
    normalize_assessment,
)

from app.services.assessment_image_caption import (
    caption_assessment_image,
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
MODEL_VERSION = "grouped-cls-20261118-species-policy-v1"

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

        notify_assessment_finished(db, job)

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


_model_process = local()

def uploaded_pet_species(image_id):
    with SessionLocal() as db:
        image = db.get(DentalImage, image_id)

        if image is None:
            raise ValueError("Uploaded image record is missing.")

        pet = db.get(Pet, image.pet_id)

        if pet is None:
            raise ValueError("Pet record is missing.")

        aliases = {
            "cat": "cat",
            "feline": "cat",
            "dog": "dog",
            "canine": "dog",
        }

        species = aliases.get(str(pet.species).strip().lower())

        if species is None:
            raise ValueError("Dental assessment supports cats and dogs.")

        return species

def run_models(image_path, output_directory, stop_event, species):
    client = getattr(_model_process, "client", None)

    if client is None:
        client = ModelProcessClient(RUNNER, timeout=PROCESS_TIMEOUT)
        _model_process.client = client

    return client.run(
        image_path,
        output_directory,
        stop_event,
        species=species,
    )


def validate_predictions(result):
    predictions = result.get("predictions")

    if not isinstance(predictions, dict):
        raise ValueError("Prediction results are missing.")

    if set(predictions) != set(CONDITIONS):
        raise ValueError("Unexpected prediction conditions.")

    for condition in CONDITIONS:
        prediction = predictions[condition]

        if not isinstance(prediction, dict):
            raise ValueError("Invalid prediction result.")

        confidence = prediction.get("confidence")
        threshold = prediction.get("threshold")

        for value in (confidence, threshold):
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                raise ValueError("Invalid prediction score.")

        # Older runner results remain compatible.
        assessed = prediction.get("assessed", True)

        if type(assessed) is not bool:
            raise ValueError("Invalid assessment support flag.")

        raw_positive = prediction.get(
            "raw_positive",
            prediction.get("positive"),
        )

        if type(raw_positive) is not bool:
            raise ValueError("Invalid raw prediction decision.")

        if raw_positive != (confidence >= threshold):
            raise ValueError("Prediction threshold mismatch.")

        positive = prediction.get("positive")

        if assessed:
            if type(positive) is not bool or positive != raw_positive:
                raise ValueError("Invalid assessed prediction.")
        elif positive is not None:
            raise ValueError(
                "An unsupported prediction must have positive=None."
            )

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
                    # Retain the raw threshold decision for traceability.
                    # supported=False excludes it from interpretation.
                    predicted_positive=prediction.get(
                        "raw_positive",
                        prediction["positive"],
                    ),
                    supported=prediction.get("assessed", True),
                )
            )

            public_predictions.append({
                "condition": condition,
                "confidence": prediction["confidence"],
                "threshold": prediction["threshold"],
                "positive": prediction["positive"],
                "assessed": prediction.get("assessed", True),
                "assessment_note": prediction.get("assessment_note"),
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
            "segmentation_palette": "red-yellow-v1",
            "predictions": public_predictions,
            "segmentation": extract_segmentation_metrics(
                result.get("segmentation")
            ),
            "severity": {
                "label": severity["severity"],
                "method": "experimental_rule_based",
                "reason": severity.get("reason"),
                "calculation_version": severity.get(
                    "calculation_version"
                ),
                "scored_conditions": severity.get(
                    "scored_conditions", []
                ),
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
        
        job.result_summary = normalize_assessment(
            job.result_summary
        )

        for image_kind in (
            "heatmap",
            "segmentation",
            "summary",
        ):
            caption_assessment_image(
                attempt_directory / f"{image_kind}.png",
                job.result_summary,
                image_kind,
            )

        notify_assessment_finished(db, job)       

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

        species = uploaded_pet_species(image_id)

        payload = run_models(
            image_path,
            attempt_directory,
            stop_event,
            species=species,
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
    try:
        while not stop_event.is_set():
            try:
                claimed = claim_job()

                if claimed is not None:
                    process_job(claimed, stop_event)
                    continue

            except Exception:
                logger.exception("Dental assessment worker failed")

            stop_event.wait(3)
    finally:
        client = getattr(_model_process, "client", None)
        if client is not None:
            client.close()
            del _model_process.client
