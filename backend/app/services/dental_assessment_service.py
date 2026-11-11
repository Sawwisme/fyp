from datetime import datetime, timezone

from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.models import DentalAssessmentJob, DentalImage, Pet
from app.services.dental_image_service import get_image_path
from app.services.pet_service import get_owner_profile


def _owned_image(db, current_user, image_id, lock=False):
    owner = get_owner_profile(db, current_user)

    statement = (
        select(DentalImage)
        .join(Pet, Pet.pet_id == DentalImage.pet_id)
        .where(
            DentalImage.dental_image_id == image_id,
            DentalImage.uploaded_by == current_user.user_id,
            Pet.pet_owner_id == owner.pet_owner_id,
        )
    )

    if lock:
        statement = statement.with_for_update()

    image = db.scalar(statement)

    if image is None:
        raise HTTPException(404, "Dental image not found.")

    return image


def _timestamp(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def _serialize(job):
    return {
        "assessment_job_id": job.assessment_job_id,
        "dental_image_id": job.dental_image_id,
        "analysis_id": job.analysis_id,
        "status": job.status,
        "created_at": _timestamp(job.created_at),
        "started_at": _timestamp(job.started_at),
        "finished_at": _timestamp(job.finished_at),
        "message": job.error_message,
        "result": (
            job.result_summary
            if job.status == "completed"
            else None
        ),
    }


def queue_assessment(db, current_user, image_id):
    try:
        # Lock the uploaded image to serialize duplicate start requests.
        _owned_image(
            db,
            current_user,
            image_id,
            lock=True,
        )

        existing = db.scalar(
            select(DentalAssessmentJob)
            .where(
                DentalAssessmentJob.dental_image_id == image_id
            )
            .with_for_update()
        )

        if existing is not None:
            response = _serialize(existing)
            db.commit()
            return response

        # Confirm that the owner's uploaded file still exists.
        # This never reads an image from the training dataset.
        get_image_path(db, current_user, image_id)

        job = DentalAssessmentJob(
            dental_image_id=image_id,
            status="queued",
            attempts=0,
            created_at=datetime.now(timezone.utc).replace(
                tzinfo=None
            ),
        )

        db.add(job)
        db.flush()

        response = _serialize(job)
        db.commit()

        return response

    except Exception:
        db.rollback()
        raise


def get_assessment(db, current_user, job_id):
    owner = get_owner_profile(db, current_user)

    record = db.execute(
        select(
            DentalAssessmentJob,
            Pet.pet_id,
        )
        .select_from(DentalAssessmentJob)
        .join(
            DentalImage,
            DentalImage.dental_image_id
            == DentalAssessmentJob.dental_image_id,
        )
        .join(
            Pet,
            Pet.pet_id == DentalImage.pet_id,
        )
        .where(
            DentalAssessmentJob.assessment_job_id == job_id,
            DentalImage.uploaded_by == current_user.user_id,
            Pet.pet_owner_id == owner.pet_owner_id,
        )
    ).one_or_none()

    if record is None:
        raise HTTPException(404, "Assessment not found.")

    job, pet_id = record

    response = _serialize(job)
    response["pet_id"] = pet_id

    return response

def get_result_image_path(db, current_user, job_id, kind):
    # This checks that the assessment belongs to the logged-in owner.
    assessment = get_assessment(
        db,
        current_user,
        job_id,
    )

    if assessment["status"] != "completed":
        raise HTTPException(
            409,
            "Assessment images are not ready yet.",
        )

    filenames = {
        "heatmap": "heatmap.png",
        "segmentation": "segmentation.png",
        "summary": "summary.png",
    }

    filename = filenames.get(kind)

    if filename is None:
        raise HTTPException(404, "Result image not found.")

    job = db.get(DentalAssessmentJob, job_id)

    try:
        token = str(UUID(job.claim_token))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            404,
            "Result image not available.",
        ) from None

    directory = (
        Path(__file__).resolve().parents[2]
        / "private_uploads"
        / "dental_assessments"
        / str(job_id)
        / token
    ).resolve()

    target = (directory / filename).resolve()

    if target.parent != directory or not target.is_file():
        raise HTTPException(
            404,
            "Result image file not found.",
        )

    return target