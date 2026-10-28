import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    Consultation,
    FollowupCare,
    FollowupImage,
    FollowupSubmission,
    Pet,
    User,
)
from app.services.followup_uploads import UPLOAD_DIRECTORY
from app.services.pet_service import get_owner_profile
from app.services.vet_profile_service import get_profile


def get_photo_path(
    db: Session,
    current_user: User,
    image_id: int,
):
    statement = (
        select(FollowupImage)
        .join(
            FollowupSubmission,
            (
                FollowupSubmission.submission_id
                == FollowupImage.submission_id
            )
            & (
                FollowupSubmission.followup_care_id
                == FollowupImage.followup_care_id
            ),
        )
        .join(
            FollowupCare,
            FollowupCare.followup_care_id
            == FollowupImage.followup_care_id,
        )
        .join(
            Consultation,
            Consultation.consultation_id
            == FollowupCare.consultation_id,
        )
        .join(
            Appointment,
            Appointment.appointment_id
            == Consultation.appointment_id,
        )
        .join(Pet, Pet.pet_id == FollowupCare.pet_id)
        .where(
            FollowupImage.followup_care_image_id == image_id,
            FollowupCare.pet_id == Consultation.pet_id,
            Consultation.status == "completed",
        )
    )

    if current_user.role == "pet_owner":
        owner = get_owner_profile(db, current_user)

        statement = statement.where(
            FollowupSubmission.pet_owner_id == owner.pet_owner_id,
            Pet.pet_owner_id == owner.pet_owner_id,
            Appointment.pet_owner_id == owner.pet_owner_id,
        )

    elif current_user.role == "veterinarian":
        veterinarian = get_profile(db, current_user)

        statement = statement.where(
            FollowupCare.veterinarian_id
            == veterinarian.veterinarian_id,
            Consultation.clinic_id == veterinarian.clinic_id,
        )

    else:
        raise HTTPException(403, "Photo access is not allowed.")

    image = db.scalar(statement)

    if image is None:
        raise HTTPException(404, "Photo not found.")

    # New uploads use generated filenames, never client paths.
    if not re.fullmatch(r"[0-9a-f]{32}\.jpg", image.image_url):
        raise HTTPException(404, "Photo not available.")

    directory = UPLOAD_DIRECTORY.resolve()
    target = (directory / image.image_url).resolve()

    if target.parent != directory or not target.is_file():
        raise HTTPException(404, "Photo file not found.")

    return target