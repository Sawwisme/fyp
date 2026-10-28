from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Appointment,
    Consultation,
    FollowupCare,
    FollowupImage,
    FollowupSubmission,
    Pet,
    User,
)
from app.schemas.followup_submissions import (
    FollowupSubmissionResponse,
)
from app.services.followup_uploads import (
    UPLOAD_DIRECTORY,
    prepare_photo,
    save_photo,
)
from app.services.pet_service import get_owner_profile


def owner_followup_query(owner_id: int, followup_id: int):
    return (
        select(FollowupCare)
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
            FollowupCare.followup_care_id == followup_id,
            FollowupCare.pet_id == Consultation.pet_id,
            Consultation.status == "completed",
            Appointment.pet_owner_id == owner_id,
            Pet.pet_owner_id == owner_id,
        )
    )


def create_submission(
    db: Session,
    current_user: User,
    followup_id: int,
    owner_comment: str | None,
    files: list[UploadFile],
):
    written_files = []
    committing = False

    try:
        owner = get_owner_profile(db, current_user)

        followup = db.scalar(
            owner_followup_query(
                owner.pet_owner_id,
                followup_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if followup is None:
            raise HTTPException(404, "Follow-up not found.")

        if followup.status != "pending":
            raise HTTPException(
                409,
                "This follow-up no longer accepts submissions.",
            )

        if len(files) > 4:
            raise HTTPException(
                422,
                "Submit up to four photos at a time.",
            )

        comment = (owner_comment or "").strip() or None

        if comment and len(comment) > 5000:
            raise HTTPException(422, "The comment is too long.")

        if followup.photos_required and not files:
            raise HTTPException(
                422,
                "Your veterinarian requires a photo submission.",
            )

        if not files and not comment:
            raise HTTPException(
                422,
                "Add a photo or a progress comment.",
            )

        # Validate every photo before writing any files.
        prepared = [prepare_photo(photo) for photo in files]

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        submission = FollowupSubmission(
            followup_care_id=followup.followup_care_id,
            pet_owner_id=owner.pet_owner_id,
            owner_comment=comment,
            submitted_at=now,
            review_status="submitted",
        )

        db.add(submission)
        db.flush()

        for content in prepared:
            filename = save_photo(content)
            written_files.append(filename)

            submission.images.append(
                FollowupImage(
                    followup_care_id=followup.followup_care_id,
                    image_url=filename,
                    uploaded_at=now,
                )
            )

        db.flush()

        result = FollowupSubmissionResponse.model_validate(
            submission
        )

        committing = True
        db.commit()

        return result

    except Exception:
        db.rollback()

        # Before commit, files can safely be removed.
        # If commit outcome is uncertain, retain them to avoid
        # deleting photos referenced by a saved submission.
        if not committing:
            for filename in written_files:
                (UPLOAD_DIRECTORY / filename).unlink(
                    missing_ok=True
                )

        raise


def list_owner_submissions(
    db: Session,
    current_user: User,
    followup_id: int,
    offset: int,
    limit: int,
):
    owner = get_owner_profile(db, current_user)

    followup = db.scalar(
        owner_followup_query(owner.pet_owner_id, followup_id)
    )

    if followup is None:
        raise HTTPException(404, "Follow-up not found.")

    return db.scalars(
        select(FollowupSubmission)
        .where(
            FollowupSubmission.followup_care_id == followup_id,
            FollowupSubmission.pet_owner_id == owner.pet_owner_id,
        )
        .options(selectinload(FollowupSubmission.images))
        .order_by(
            FollowupSubmission.submitted_at.desc(),
            FollowupSubmission.submission_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()