from fastapi import HTTPException
from sqlalchemy import select

from app.models import AIAnalysisResult, DentalAssessmentJob, DentalImage


def validate_scan_booking(db, current_user, pet, analysis_id):
    if analysis_id is None:
        return

    assessment = db.scalar(
        select(AIAnalysisResult)
        .join(
            DentalImage,
            DentalImage.dental_image_id
            == AIAnalysisResult.dental_image_id,
        )
        .join(
            DentalAssessmentJob,
            DentalAssessmentJob.analysis_id
            == AIAnalysisResult.analysis_id,
        )
        .where(
            AIAnalysisResult.analysis_id == analysis_id,
            DentalImage.uploaded_by == current_user.user_id,
            DentalImage.pet_id == pet.pet_id,
            DentalAssessmentJob.dental_image_id
            == DentalImage.dental_image_id,
            DentalAssessmentJob.status == "completed",
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if assessment is None:
        raise HTTPException(
            404,
            "Completed assessment not found for this pet.",
        )