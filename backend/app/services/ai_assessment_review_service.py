from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import re
from pathlib import Path
from uuid import UUID

from app.models import (
    AIAssessmentReview,
    AIAnalysisResult,
    Clinic,
    DentalAssessmentJob,
    DentalImage,
    Notification,
    Pet,
    User,
    Veterinarian,
)
from app.services.pet_service import get_owner_profile
from app.services.vet_profile_service import get_profile


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def timestamp(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def serialize_review(record):
    analysis = record.analysis
    image = analysis.dental_image
    pet = image.pet
    reviewer = record.reviewed_by

    return {
        "review_id": record.review_id,
        "analysis_id": record.analysis_id,
        "clinic_id": record.clinic_id,
        "clinic_name": record.clinic.clinic_name,
        "pet_id": pet.pet_id,
        "pet_name": pet.pet_name,
        "species": pet.species,
        "owner_name": record.requested_by.full_name,
        "status": record.status,
        "owner_message": record.owner_message,
        "requested_at": timestamp(record.requested_at),
        "reviewed_at": timestamp(record.reviewed_at),
        "reviewed_by_veterinarian_id": (
            record.reviewed_by_veterinarian_id
        ),
        "reviewed_by_name": (
            reviewer.user.full_name if reviewer else None
        ),
        "reviewed_severity": record.reviewed_severity,
        "recommended_action": record.recommended_action,
        "feedback": record.feedback,
        "model_version": analysis.model_version,
        "media": {
            kind: (
                f"/ai-assessment-reviews/"
                f"{record.review_id}/media/{kind}"
            )
            for kind in (
                "original",
                "heatmap",
                "segmentation",
                "summary",
            )
        },
        "predictions": [
            {
                "condition": prediction.condition_name,
                "confidence": float(prediction.confidence_score),
                "positive": prediction.predicted_positive,
                "supported": prediction.supported,
            }
            for prediction in analysis.predictions
        ],
    }


def visible_statement(db, current_user):
    statement = (
        select(AIAssessmentReview)
        .join(
            AIAnalysisResult,
            AIAnalysisResult.analysis_id
            == AIAssessmentReview.analysis_id,
        )
        .join(
            DentalImage,
            DentalImage.dental_image_id
            == AIAnalysisResult.dental_image_id,
        )
        .join(Pet, Pet.pet_id == DentalImage.pet_id)
        .options(
            selectinload(AIAssessmentReview.analysis)
            .selectinload(AIAnalysisResult.predictions),
            selectinload(AIAssessmentReview.analysis)
            .selectinload(AIAnalysisResult.dental_image)
            .selectinload(DentalImage.pet),
            selectinload(AIAssessmentReview.clinic),
            selectinload(AIAssessmentReview.requested_by),
            selectinload(AIAssessmentReview.reviewed_by)
            .selectinload(Veterinarian.user),
        )
    )

    if current_user.role == "pet_owner":
        owner = get_owner_profile(db, current_user)

        return statement.where(
            AIAssessmentReview.requested_by_user_id
            == current_user.user_id,
            DentalImage.uploaded_by == current_user.user_id,
            Pet.pet_owner_id == owner.pet_owner_id,
        )

    if current_user.role == "veterinarian":
        veterinarian = get_profile(db, current_user)

        return statement.where(
            AIAssessmentReview.clinic_id
            == veterinarian.clinic_id,
            AIAssessmentReview.status != "cancelled",
        )

    raise HTTPException(403, "You cannot access assessment reviews.")


def get_review_record(
    db,
    current_user,
    review_id,
    lock=False,
):
    statement = visible_statement(db, current_user).where(
        AIAssessmentReview.review_id == review_id,
    )

    if lock:
        statement = (
            statement
            .execution_options(populate_existing=True)
            .with_for_update()
        )

    record = db.scalar(statement)

    if record is None:
        raise HTTPException(404, "Assessment review not found.")

    return record


def get_review(db, current_user, review_id):
    record = get_review_record(db, current_user, review_id)
    response = serialize_review(record)

    job = db.scalar(
        select(DentalAssessmentJob).where(
            DentalAssessmentJob.analysis_id == record.analysis_id,
            DentalAssessmentJob.status == "completed",
        )
    )

    summary = (
        job.result_summary
        if job is not None and isinstance(job.result_summary, dict)
        else {}
    )

    severity = summary.get("severity")

    response["ai_severity"] = (
        {
            "label": severity.get("label"),
            "method": severity.get("method"),
            "reason": severity.get("reason"),
        }
        if isinstance(severity, dict)
        else None
    )

    return response


def list_reviews(
    db,
    current_user,
    review_status,
    offset,
    limit,
):
    statement = visible_statement(db, current_user)

    if review_status is not None:
        statement = statement.where(
            AIAssessmentReview.status == review_status,
        )

    records = db.scalars(
        statement
        .order_by(
            AIAssessmentReview.requested_at.desc(),
            AIAssessmentReview.review_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return [serialize_review(record) for record in records]


def request_review(db, current_user, analysis_id, data):
    if current_user.role != "pet_owner":
        raise HTTPException(403, "A pet owner account is required.")

    try:
        owner = get_owner_profile(db, current_user)

        # Lock the owned assessment to serialize duplicate requests.
        analysis = db.scalar(
            select(AIAnalysisResult)
            .join(
                DentalImage,
                DentalImage.dental_image_id
                == AIAnalysisResult.dental_image_id,
            )
            .join(Pet, Pet.pet_id == DentalImage.pet_id)
            .where(
                AIAnalysisResult.analysis_id == analysis_id,
                DentalImage.uploaded_by == current_user.user_id,
                Pet.pet_owner_id == owner.pet_owner_id,
            )
            .with_for_update()
        )

        if analysis is None:
            raise HTTPException(404, "Assessment not found.")

        completed_job = db.scalar(
            select(DentalAssessmentJob.assessment_job_id)
            .where(
                DentalAssessmentJob.analysis_id == analysis_id,
                DentalAssessmentJob.status == "completed",
            )
        )

        if completed_job is None:
            raise HTTPException(
                409,
                "Only completed assessments can be submitted for review.",
            )

        existing = db.scalar(
            select(AIAssessmentReview)
            .where(
                AIAssessmentReview.analysis_id == analysis_id,
                AIAssessmentReview.clinic_id == data.clinic_id,
            )
            .with_for_update()
        )

        if existing is not None:
            if (
                existing.requested_by_user_id
                != current_user.user_id
            ):
                raise HTTPException(404, "Assessment review not found.")

            if existing.status == "cancelled":
                raise HTTPException(
                    409,
                    "This review request has been cancelled.",
                )

            response = serialize_review(existing)
            db.commit()
            return response

        clinic = db.scalar(
            select(Clinic).where(
                Clinic.clinic_id == data.clinic_id,
                Clinic.status == "active",
            )
        )

        if clinic is None:
            raise HTTPException(404, "Active clinic not found.")

        veterinarian_user_ids = db.scalars(
            select(Veterinarian.user_id)
            .join(User, User.user_id == Veterinarian.user_id)
            .where(
                Veterinarian.clinic_id == clinic.clinic_id,
                Veterinarian.approval_status == "approved",
                User.role == "veterinarian",
                User.status == "active",
            )
        ).all()

        if not veterinarian_user_ids:
            raise HTTPException(
                409,
                "This clinic has no available veterinarian accounts "
                "to receive a review request.",
            )

        record = AIAssessmentReview(
            analysis_id=analysis_id,
            clinic_id=clinic.clinic_id,
            requested_by_user_id=current_user.user_id,
            status="pending",
            owner_message=data.owner_message,
            requested_at=utc_now(),
        )

        db.add(record)
        db.flush()

        for user_id in veterinarian_user_ids:
            db.add(
                Notification(
                    user_id=user_id,
                    event_key=f"ai-review-request:{record.review_id}",
                    notification_type="ai_review_requested",
                    title="New dental assessment review",
                    message=(
                        "An owner shared a dental assessment "
                        "with your clinic for review."
                    ),
                    resource_type="ai_assessment_review",
                    resource_id=record.review_id,
                )
            )

        response = serialize_review(record)
        db.commit()
        return response

    except Exception:
        db.rollback()
        raise


def submit_review(db, current_user, review_id, data):
    if current_user.role != "veterinarian":
        raise HTTPException(403, "A veterinarian account is required.")

    try:
        veterinarian = get_profile(db, current_user)

        record = get_review_record(
            db,
            current_user,
            review_id,
            lock=True,
        )

        if record.status != "pending":
            raise HTTPException(
                409,
                "This request is no longer awaiting review. "
                "Refresh to view its saved result.",
            )

        record.reviewed_by_veterinarian_id = (
            veterinarian.veterinarian_id
        )
        record.reviewed_severity = data.reviewed_severity
        record.recommended_action = data.recommended_action
        record.feedback = data.feedback
        record.reviewed_at = utc_now()
        record.status = "reviewed"

        db.add(
            Notification(
                user_id=record.requested_by_user_id,
                event_key=f"ai-review-completed:{record.review_id}",
                notification_type="ai_review_completed",
                title="Your dental assessment has been reviewed",
                message=(
                    "A veterinarian has reviewed your assessment. "
                    "Open the review to read their feedback "
                    "and recommended next action."
                ),
                resource_type="ai_assessment_review",
                resource_id=record.review_id,
            )
        )

        db.flush()

        # Reload the relationship if it was previously loaded as None.
        db.expire(record, ["reviewed_by"])

        response = serialize_review(record)
        db.commit()
        return response

    except Exception:
        db.rollback()
        raise

def get_review_media_path(
    db,
    current_user,
    review_id,
    kind,
):
    # Authorize every image request through the review.
    # This checks owner identity or approved vet clinic membership.
    record = get_review_record(
        db,
        current_user,
        review_id,
    )

    private_root = (
        Path(__file__).resolve().parents[2]
        / "private_uploads"
    ).resolve()

    if kind == "original":
        filename = record.analysis.dental_image.image_url

        if not re.fullmatch(r"[0-9a-f]{32}\.jpg", filename):
            raise HTTPException(404, "Original image unavailable.")

        directory = (private_root / "dental_images").resolve()
        target = (directory / filename).resolve()

    else:
        filenames = {
            "heatmap": "heatmap.png",
            "segmentation": "segmentation.png",
            "summary": "summary.png",
        }

        filename = filenames.get(kind)

        if filename is None:
            raise HTTPException(404, "Result image not found.")

        job = db.scalar(
            select(DentalAssessmentJob).where(
                DentalAssessmentJob.analysis_id
                == record.analysis_id,
                DentalAssessmentJob.dental_image_id
                == record.analysis.dental_image_id,
                DentalAssessmentJob.status == "completed",
            )
        )

        if job is None:
            raise HTTPException(404, "Assessment images unavailable.")

        try:
            token = str(UUID(job.claim_token))
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                404,
                "Assessment images unavailable.",
            ) from None

        directory = (
            private_root
            / "dental_assessments"
            / str(job.assessment_job_id)
            / token
        ).resolve()

        target = (directory / filename).resolve()

    if (
        not directory.is_relative_to(private_root)
        or target.parent != directory
        or not target.is_file()
    ):
        raise HTTPException(404, "Image file not found.")

    return target