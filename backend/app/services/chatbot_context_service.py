from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    AIAnalysisResult,
    AIAssessmentReview,
    DentalAssessmentJob,
    DentalImage,
    Appointment,
    Consultation,
)
from app.services.pet_service import get_owner_profile, get_pet
from app.services.dental_result_metrics import (
    extract_segmentation_metrics,
)


def iso_utc(value):
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.isoformat()


def analysis_context(job, analysis):
    summary = (
        job.result_summary
        if isinstance(job.result_summary, dict)
        else {}
    )

    predictions = []
    detected_conditions = []

    raw_predictions = summary.get("predictions", [])

    if not isinstance(raw_predictions, list):
        raw_predictions = []

    for item in raw_predictions:
        if not isinstance(item, dict):
            continue

        condition = item.get("condition")

        if condition not in {
            "healthy",
            "plaque",
            "gingivitis",
            "calculus",
        }:
            continue

        confidence = item.get("confidence")

        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            confidence = None

        positive = item.get("positive") is True

        predictions.append({
            "condition": condition,
            "confidence": confidence,
            "positive": positive,
        })

        if positive:
            detected_conditions.append(condition)

    raw_severity = summary.get("severity")
    severity = None
    severity_method = None

    if isinstance(raw_severity, dict):
        label = raw_severity.get("label")

        if isinstance(label, str):
            label = label.lower()

            if label in {"none", "mild", "moderate", "severe"}:
                severity = label

        severity_method = raw_severity.get("method")

    return {
        "analysis_id": analysis.analysis_id,
        "assessment_job_id": job.assessment_job_id,
        "analysis_date": iso_utc(analysis.analysis_date),
        "model_version": analysis.model_version,
        "detected_conditions": detected_conditions,
        "predictions": predictions,
        "estimated_severity": severity,
        "severity_method": severity_method,

        # Availability only: never expose local file paths.
        "gradcam": {
            "available": bool(analysis.heatmap_url),
            "meaning": "classification_attention",
        },
        "segmentation": {
            "available": bool(analysis.segmentation_url),
            **extract_segmentation_metrics(
                summary.get("segmentation")
            ),
        },
    }


def build_chat_context(db, current_user, pet_id):
    if current_user.role != "pet_owner":
        raise HTTPException(
            403,
            "A pet owner account is required.",
        )

    owner = get_owner_profile(db, current_user)

    context = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "context_status": "select_pet",
        "pet": None,
        "latest_analysis": None,
        "dental_history": [],
        "vet_reviews": [],
        "latest_consultation": None,
    }

    # General questions can work without selecting a pet.
    if pet_id is None:
        return context

    # This helper checks that the pet belongs to this owner.
    pet = get_pet(db, current_user, pet_id)

    context["context_status"] = "available"
    context["pet"] = {
        "pet_id": pet.pet_id,
        "name": pet.pet_name,
        "species": pet.species,
        "breed": pet.breed,
        "gender": pet.gender,
        "date_of_birth": (
            pet.date_of_birth.isoformat()
            if pet.date_of_birth is not None
            else None
        ),
    }

    # Retrieve only a completed consultation for this owner's pet.
    consultation = db.scalar(
        select(Consultation)
        .join(
            Appointment,
            Appointment.appointment_id == Consultation.appointment_id,
        )
        .where(
            Consultation.pet_id == pet.pet_id,
            Appointment.pet_id == pet.pet_id,
            Appointment.pet_owner_id == owner.pet_owner_id,
            Consultation.status == "completed",
        )
        .order_by(
            Consultation.consultation_date.desc(),
            Consultation.consultation_id.desc(),
        )
        .limit(1)
    )

    if consultation is not None:
        context["latest_consultation"] = {
            "consultation_id": consultation.consultation_id,
            "clinic_id": consultation.clinic_id,
            "consultation_date": iso_utc(
                consultation.consultation_date
            ),
            "diagnosis": consultation.diagnosis,
            "home_care_instructions": (
                consultation.followup_instructions
            ),
            "followup_required": consultation.followup_required,
            "in_clinic_review_required": (
                consultation.followup_visit_required
            ),
        }

    records = db.execute(
        select(DentalAssessmentJob, AIAnalysisResult)
        .join(
            AIAnalysisResult,
            AIAnalysisResult.analysis_id
            == DentalAssessmentJob.analysis_id,
        )
        .join(
            DentalImage,
            DentalImage.dental_image_id
            == AIAnalysisResult.dental_image_id,
        )
        .where(
            DentalAssessmentJob.status == "completed",
            DentalAssessmentJob.dental_image_id
            == DentalImage.dental_image_id,
            DentalImage.pet_id == pet.pet_id,
            DentalImage.uploaded_by == current_user.user_id,
        )
        .order_by(
            AIAnalysisResult.analysis_date.desc(),
            AIAnalysisResult.analysis_id.desc(),
        )
        .limit(5)
    ).all()

    history = [
        analysis_context(job, analysis)
        for job, analysis in records
    ]

    context["dental_history"] = history
    context["latest_analysis"] = history[0] if history else None

    if not history:
        return context

    analysis_ids = [
        item["analysis_id"]
        for item in history
    ]

    reviews = db.scalars(
        select(AIAssessmentReview)
        .where(
            AIAssessmentReview.analysis_id.in_(analysis_ids),
            AIAssessmentReview.requested_by_user_id
            == current_user.user_id,
            AIAssessmentReview.status == "reviewed",
        )
        .order_by(
            AIAssessmentReview.reviewed_at.desc(),
            AIAssessmentReview.review_id.desc(),
        )
        .limit(5)
    ).all()

    context["vet_reviews"] = [
        {
            "review_id": review.review_id,
            "analysis_id": review.analysis_id,
            "clinic_id": review.clinic_id,
            "reviewed_severity": review.reviewed_severity,
            "recommended_action": review.recommended_action,
            "feedback": review.feedback,
            "reviewed_at": iso_utc(review.reviewed_at),
        }
        for review in reviews
    ]

    return context