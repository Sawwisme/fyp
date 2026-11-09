from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    AIAssessmentReview,
    AIAnalysisResult,
    Appointment,
    DentalImage,
)


def validate_review_booking(
    db,
    current_user,
    pet,
    clinic,
    review_id,
):
    if review_id is None:
        return

    # The caller must already have checked and locked the owner's pet.
    review = db.scalar(
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
        .where(
            AIAssessmentReview.review_id == review_id,
            AIAssessmentReview.requested_by_user_id
            == current_user.user_id,
            AIAssessmentReview.clinic_id == clinic.clinic_id,
            DentalImage.uploaded_by == current_user.user_id,
            DentalImage.pet_id == pet.pet_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if review is None:
        raise HTTPException(
            404,
            "Assessment review not found for this pet and clinic.",
        )

    if review.status != "reviewed":
        raise HTTPException(
            409,
            "This assessment has not received a completed vet review.",
        )

    if review.recommended_action not in {
        "routine_booking",
        "prompt_clinic_assessment",
    }:
        raise HTTPException(
            409,
            "This review does not recommend a clinic appointment.",
        )

    # A locking read sees the latest bookings, including concurrent ones.
    existing = db.scalar(
        select(Appointment.appointment_id)
        .where(
            Appointment.ai_assessment_review_id == review_id,
            Appointment.status.notin_(["cancelled", "rejected"]),
        )
        .limit(1)
        .with_for_update()
    )

    if existing is not None:
        raise HTTPException(
            409,
            "This review already has an appointment. "
            "Open that appointment to manage it.",
        )