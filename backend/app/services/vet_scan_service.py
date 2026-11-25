from datetime import timezone
import re
from pathlib import Path
from uuid import UUID

from app.services.dental_image_service import UPLOAD_DIRECTORY
from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    AIAnalysisResult,
    Appointment,
    DentalAssessmentJob,
    DentalImage,
    Pet,
    PetOwner,
    Schedule,
    TimeSlot,
)
from app.services.assessment_interpretation import normalize_assessment
from app.services.vet_profile_service import get_profile


def _timestamp(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_linked_scan(db, current_user, appointment_id):
    veterinarian = get_profile(db, current_user)

    record = db.execute(
        select(Appointment, DentalAssessmentJob, Pet)
        .select_from(Appointment)
        .join(
            TimeSlot,
            TimeSlot.time_slot_id == Appointment.time_slot_id,
        )
        .join(
            Schedule,
            Schedule.schedule_id == TimeSlot.schedule_id,
        )
        .join(Pet, Pet.pet_id == Appointment.pet_id)
        .join(
            PetOwner,
            PetOwner.pet_owner_id == Appointment.pet_owner_id,
        )
        .join(
            AIAnalysisResult,
            AIAnalysisResult.analysis_id == Appointment.ai_analysis_id,
        )
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
            Appointment.appointment_id == appointment_id,
            Appointment.veterinarian_id
            == veterinarian.veterinarian_id,
            Schedule.veterinarian_id
            == veterinarian.veterinarian_id,
            Appointment.status.in_([
                "confirmed",
                "in_progress",
                "completed",
            ]),
            Pet.pet_owner_id == Appointment.pet_owner_id,
            DentalImage.pet_id == Appointment.pet_id,
            DentalImage.uploaded_by == PetOwner.user_id,
            DentalAssessmentJob.dental_image_id
            == DentalImage.dental_image_id,
            DentalAssessmentJob.status == "completed",
        )
    ).one_or_none()

    if record is None:
        raise HTTPException(
            404,
            "Linked assessment not available for this appointment.",
        )

    appointment, job, pet = record

    return {
        "appointment_id": appointment.appointment_id,
        "analysis_id": appointment.ai_analysis_id,
        "assessment_job_id": job.assessment_job_id,
        "pet_id": pet.pet_id,
        "pet_name": pet.pet_name,
        "species": pet.species,
        "created_at": _timestamp(job.created_at),
        "finished_at": _timestamp(job.finished_at),
        "result": normalize_assessment(job.result_summary),
    }

def get_linked_scan_media(db, current_user, appointment_id, kind):
    # Recheck the assigned vet and appointment access for every image.
    assessment = get_linked_scan(
        db, current_user, appointment_id
    )

    job = db.get(
        DentalAssessmentJob,
        assessment["assessment_job_id"],
    )

    if job is None:
        raise HTTPException(404, "Assessment image not available.")

    if kind == "original":
        image = db.get(DentalImage, job.dental_image_id)

        if image is None or not re.fullmatch(
            r"[0-9a-f]{32}\.jpg",
            image.image_url or "",
        ):
            raise HTTPException(404, "Original photo not available.")

        directory = UPLOAD_DIRECTORY.resolve()
        target = (directory / image.image_url).resolve()

    else:
        filenames = {
            "heatmap": "heatmap.png",
            "segmentation": "segmentation.png",
            "summary": "summary.png",
        }

        filename = filenames.get(kind)

        if filename is None:
            raise HTTPException(404, "Assessment image not found.")

        try:
            token = str(UUID(job.claim_token))
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                404, "Assessment image not available."
            ) from None

        directory = (
            Path(__file__).resolve().parents[2]
            / "private_uploads"
            / "dental_assessments"
            / str(job.assessment_job_id)
            / token
        ).resolve()

        target = (directory / filename).resolve()

    if target.parent != directory or not target.is_file():
        raise HTTPException(404, "Assessment image file not found.")

    return target