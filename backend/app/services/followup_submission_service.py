from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile
from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from app.services.vet_profile_service import get_profile

from app.models import (
    Appointment,
    Consultation,
    FollowupCare,
    FollowupImage,
    FollowupSubmission,
    Pet,
    User,
    FollowupReviewDecision,
    Clinic,
)
from app.schemas.followup_submissions import (
    FollowupSubmissionResponse,
    FollowupSubmissionReview,
)
from app.services.followup_uploads import (
    UPLOAD_DIRECTORY,
    prepare_photo,
    save_photo,
    validate_prepared_photos,
)
from app.services.pet_service import get_owner_profile
from app.services.notification_service import notify_followup_reviewed

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
    try:
        # Authorise before expensive inference; the final locked function
        # repeats ownership and state checks to handle concurrent changes.
        owner = get_owner_profile(db, current_user)
        followup = db.scalar(owner_followup_query(owner.pet_owner_id, followup_id))
        if followup is None:
            raise HTTPException(404, "Follow-up not found.")
        if followup.status != "pending":
            raise HTTPException(409, "This follow-up no longer accepts submissions.")
        if len(files) > 4:
            raise HTTPException(422, "Submit up to four photos at a time.")
        comment = (owner_comment or "").strip() or None
        if comment and len(comment) > 5000:
            raise HTTPException(422, "The comment is too long.")
        if followup.photos_required and not files:
            raise HTTPException(422, "Your veterinarian requires a photo submission.")
        if not files and not comment:
            raise HTTPException(422, "Add a photo or a progress comment.")
        prepared = [prepare_photo(photo) for photo in files]
        # No row lock or read transaction remains open during inference.
        db.rollback()
        validate_prepared_photos(prepared)
        return _create_validated_submission(
            db, current_user, followup_id, owner_comment, files, prepared
        )
    except Exception:
        db.rollback()
        raise


def _create_validated_submission(
    db: Session,
    current_user: User,
    followup_id: int,
    owner_comment: str | None,
    files: list[UploadFile],
    prepared: list[bytes],
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

# The follow-up row is already locked above, so submissions
# for this task are checked and created one at a time.
        awaiting_review = db.scalar(
            select(FollowupSubmission.submission_id)
            .where(
                FollowupSubmission.followup_care_id == followup_id,
                FollowupSubmission.review_status == "submitted",
            )
            .limit(1)
        )

        if awaiting_review is not None:
            raise HTTPException(
                409,
                "Your previous update is awaiting veterinarian review. "
                "You cannot submit another update yet.",
            )

        latest_submission = db.scalar(
            select(FollowupSubmission)
            .where(
                FollowupSubmission.followup_care_id == followup_id
            )
            .order_by(
                FollowupSubmission.submitted_at.desc(),
                FollowupSubmission.submission_id.desc(),
            )
            .limit(1)
        )

        if (
            latest_submission is not None
            and latest_submission.review_status != "more_requested"
        ):
            raise HTTPException(
                409,
                "Your veterinarian has reviewed your update. "
                "You can submit again only when another update is requested.",
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

        # Photos have passed file, quality and trained-model validation.
        

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

        from app.services.staff_notification_service import notify_followup_submitted
        notify_followup_submitted(db, followup, submission)
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

def vet_followup_query(veterinarian, followup_id: int):
    return (
        select(FollowupCare)
        .join(
            Consultation,
            Consultation.consultation_id
            == FollowupCare.consultation_id,
        )
        .where(
            FollowupCare.followup_care_id == followup_id,
            FollowupCare.veterinarian_id
            == veterinarian.veterinarian_id,
            FollowupCare.pet_id == Consultation.pet_id,
            Consultation.clinic_id == veterinarian.clinic_id,
            Consultation.status == "completed",
        )
    )


def list_vet_submissions(
    db: Session,
    current_user: User,
    followup_id: int,
    offset: int,
    limit: int,
):
    veterinarian = get_profile(db, current_user)

    followup = db.scalar(
        vet_followup_query(veterinarian, followup_id)
    )

    if followup is None:
        raise HTTPException(404, "Follow-up not found.")

    return db.scalars(
        select(FollowupSubmission)
        .where(
            FollowupSubmission.followup_care_id == followup_id
        )
        .options(selectinload(FollowupSubmission.images))
        .order_by(
            FollowupSubmission.submitted_at.desc(),
            FollowupSubmission.submission_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

def review_submission(
    db: Session,
    current_user: User,
    followup_id: int,
    submission_id: int,
    data: FollowupSubmissionReview,
):
    try:
        veterinarian = get_profile(db, current_user)

        followup = db.scalar(
            vet_followup_query(veterinarian, followup_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if followup is None:
            raise HTTPException(404, "Follow-up not found.")

        if followup.status != "pending":
            raise HTTPException(
                409,
                "This follow-up is already closed.",
            )

        submission = db.scalar(
            select(FollowupSubmission)
            .where(
                FollowupSubmission.submission_id == submission_id,
                FollowupSubmission.followup_care_id == followup_id,
            )
            .options(selectinload(FollowupSubmission.images))
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if submission is None:
            raise HTTPException(404, "Submission not found.")

        correcting = submission.decision_outcome is not None

        if correcting and not data.correction_reason:
            raise HTTPException(
                409,
                "This decision is already saved. Use Correct decision "
                "and provide a correction reason.",
            )

        if not correcting and data.correction_reason is not None:
            raise HTTPException(
                422,
                "There is no saved decision to correct.",
            )

        if correcting:
            latest_id = db.scalar(
                select(FollowupSubmission.submission_id)
                .where(
                    FollowupSubmission.followup_care_id == followup_id
                )
                .order_by(
                    FollowupSubmission.submitted_at.desc(),
                    FollowupSubmission.submission_id.desc(),
                )
                .limit(1)
            )

            if latest_id != submission_id:
                raise HTTPException(
                    409,
                    "A newer owner update exists. Review that update "
                    "instead of correcting this older decision.",
                )
        expected = data.expected_reviewed_at

        if expected is not None and expected.tzinfo is not None:
            expected = expected.astimezone(timezone.utc).replace(
                tzinfo=None
            )

        if submission.reviewed_at != expected:
            raise HTTPException(
                409,
                "This review has changed. Refresh before choosing an outcome.",
            )

        if submission.review_status != "submitted":
            latest_id = db.scalar(
                select(FollowupSubmission.submission_id)
                .where(
                    FollowupSubmission.followup_care_id == followup_id
                )
                .order_by(
                    FollowupSubmission.submitted_at.desc(),
                    FollowupSubmission.submission_id.desc(),
                )
                .limit(1)
            )

            if latest_id != submission_id:
                raise HTTPException(
                    409,
                    "A newer owner update exists. Review the latest update instead.",
                )

        booked_review_id = db.scalar(
            select(Appointment.appointment_id)
            .where(
                Appointment.followup_care_id == followup_id,
                Appointment.status.notin_(["cancelled", "rejected"]),
            )
            .limit(1)
        )

        if booked_review_id is not None:
            locked_outcome = submission.decision_outcome or "in_clinic"

            if (
                data.outcome != locked_outcome
                or data.visit_waiver_reason is not None
            ):
                raise HTTPException(
                    409,
                    "A review appointment is already booked. "
                    "Only feedback can be updated; the outcome is locked.",
                )

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if data.visit_waiver_reason is not None and (
            data.outcome != "complete" or not followup.visit_required
        ):
            raise HTTPException(
                422,
                "A visit waiver applies only when completing a follow-up "
                "that currently requires an in-clinic review.",
            )

        if data.outcome == "complete":
            if followup.visit_required and not data.visit_waiver_reason:
                raise HTTPException(
                    422,
                    "Explain why the in-clinic review is no longer needed.",
                )

            linked_id = db.scalar(
                select(Appointment.appointment_id)
                .where(
                    Appointment.followup_care_id == followup_id,
                    Appointment.status.notin_(["cancelled", "rejected"]),
                )
                .limit(1)
            )

            if linked_id is not None:
                raise HTTPException(
                    409,
                    "This follow-up has a linked appointment. "
                    "Complete the review through its consultation.",
                )

            other_pending = db.scalar(
                select(FollowupSubmission.submission_id)
                .where(
                    FollowupSubmission.followup_care_id == followup_id,
                    FollowupSubmission.submission_id != submission_id,
                    FollowupSubmission.review_status == "submitted",
                )
                .limit(1)
            )

            if other_pending is not None:
                raise HTTPException(
                    409,
                    "Another update awaits review. Review it before "
                    "completing the follow-up.",
                )

        decision = FollowupReviewDecision(
            correction_reason=data.correction_reason,
            submission_id=submission.submission_id,
            veterinarian_id=veterinarian.veterinarian_id,
            previous_visit_required=followup.visit_required,
            visit_waiver_reason=data.visit_waiver_reason,
            outcome=data.outcome,
            veterinarian_comment=data.veterinarian_comment,
            decided_at=now,
            previous_review_status=submission.review_status,
            previous_comment=submission.veterinarian_comment,
            previous_reviewed_at=submission.reviewed_at,
            previous_reviewer_id=submission.reviewed_by_veterinarian_id,
        )
        db.add(decision)

        if data.outcome == "complete":
            submission.review_status = "reviewed"
            followup.visit_required = False
            followup.status = "completed"
            followup.followup_date = now
            followup.assessment_information = data.veterinarian_comment

        elif data.outcome == "request_update":
            submission.review_status = "more_requested"

        else:
            submission.review_status = "reviewed"
            followup.visit_required = True

        submission.veterinarian_comment = data.veterinarian_comment
        submission.reviewed_by_veterinarian_id = (
            veterinarian.veterinarian_id
        )
        submission.reviewed_at = now

        db.flush()
        db.expire(submission, ["decision_outcome"])

        result = FollowupSubmissionResponse.model_validate(submission)

        notify_followup_reviewed(
            db, followup, submission, decision
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise

def get_owner_submission_state(
    db: Session,
    current_user: User,
    followup_id: int,
):
    owner = get_owner_profile(db, current_user)

    followup = db.scalar(
        owner_followup_query(
            owner.pet_owner_id,
            followup_id,
        )
    )

    if followup is None:
        raise HTTPException(404, "Follow-up not found.")

    state = "reviewed"
    can_submit = False

    if followup.status in ("completed", "cancelled"):
        state = followup.status

    elif followup.status == "pending":
        awaiting_review = db.scalar(
            select(FollowupSubmission.submission_id)
            .where(
                FollowupSubmission.followup_care_id == followup_id,
                FollowupSubmission.review_status == "submitted",
            )
            .limit(1)
        )

        latest = db.scalar(
            select(FollowupSubmission)
            .where(
                FollowupSubmission.followup_care_id == followup_id
            )
            .order_by(
                FollowupSubmission.submitted_at.desc(),
                FollowupSubmission.submission_id.desc(),
            )
            .limit(1)
        )

        if awaiting_review is not None:
            state = "awaiting_review"

        elif latest is None:
            state = "action_needed"
            can_submit = True

        elif latest.review_status == "more_requested":
            state = "update_requested"
            can_submit = True

        elif followup.visit_required:
            state = "visit_required"

    return {
        "followup_care_id": followup.followup_care_id,
        "followup_status": followup.status,
        "can_submit": can_submit,
        "submission_state": state,
    }

def list_owner_followups(
    db: Session,
    current_user: User,
    task_status: str | None,
    offset: int,
    limit: int,
):
    owner = get_owner_profile(db, current_user)

    latest_status = (
        select(FollowupSubmission.review_status)
        .where(
            FollowupSubmission.followup_care_id
            == FollowupCare.followup_care_id
        )
        .order_by(
            FollowupSubmission.submitted_at.desc(),
            FollowupSubmission.submission_id.desc(),
        )
        .limit(1)
        .correlate(FollowupCare)
        .scalar_subquery()
    )

    awaiting_review = (
        select(FollowupSubmission.submission_id)
        .where(
            FollowupSubmission.followup_care_id
            == FollowupCare.followup_care_id,
            FollowupSubmission.review_status == "submitted",
        )
        .correlate(FollowupCare)
        .exists()
    )

    submission_state = case(
        (FollowupCare.status == "completed", "completed"),
        (FollowupCare.status == "cancelled", "cancelled"),
        (awaiting_review, "awaiting_review"),
        (latest_status.is_(None), "action_needed"),
        (latest_status == "more_requested", "update_requested"),
        (FollowupCare.visit_required.is_(True), "visit_required"),
        else_="reviewed",
    ).label("submission_state")

    statement = (
        select(
            FollowupCare,
            Consultation.appointment_id,
            Appointment.appointment_date,
            Pet.pet_name,
            Clinic.clinic_name,
            submission_state,
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
        .join(
            Pet,
            Pet.pet_id == FollowupCare.pet_id,
        )
        .join(
            Clinic,
            Clinic.clinic_id == Consultation.clinic_id,
        )
        .where(
            FollowupCare.pet_id == Consultation.pet_id,
            Consultation.status == "completed",
            Appointment.pet_owner_id == owner.pet_owner_id,
            Pet.pet_owner_id == owner.pet_owner_id,
        )
    )

    if task_status is not None:
        statement = statement.where(
            FollowupCare.status == task_status
        )

    records = db.execute(
        statement
        .order_by(
            Consultation.consultation_date.desc(),
            FollowupCare.followup_care_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return [
        {
            "followup_care_id": followup.followup_care_id,
            "consultation_id": followup.consultation_id,
            "appointment_id": appointment_id,
            "appointment_date": appointment_date,
            "pet_id": followup.pet_id,
            "pet_name": pet_name,
            "clinic_name": clinic_name,
            "recommended_date": followup.recommended_date,
            "followup_date": followup.followup_date,
            "reason": followup.reason,
            "care_instructions": followup.care_instructions,
            "status": followup.status,
            "photos_required": followup.photos_required,
            "photo_instructions": followup.photo_instructions,
            "visit_required": followup.visit_required,
            "submission_state": progress_state,
        }
        for (
            followup,
            appointment_id,
            appointment_date,
            pet_name,
            clinic_name,
            progress_state,
        ) in records
    ]

def get_owner_booking_context(
    db: Session,
    current_user: User,
    followup_id: int,
):
    owner = get_owner_profile(db, current_user)

    followup = db.scalar(
        owner_followup_query(
            owner.pet_owner_id,
            followup_id,
        )
    )

    if followup is None:
        raise HTTPException(404, "Follow-up not found.")

    if followup.status != "pending":
        raise HTTPException(
            409,
            "This follow-up is already closed.",
        )

    if not followup.visit_required:
        raise HTTPException(
            409,
            "An in-clinic review has not been requested.",
        )

    existing_id = db.scalar(
        select(Appointment.appointment_id)
        .where(
            Appointment.followup_care_id == followup_id,
            Appointment.status.notin_(["cancelled", "rejected"]),
        )
        .order_by(Appointment.appointment_id.desc())
        .limit(1)
    )

    consultation = followup.consultation
    veterinarian = followup.veterinarian

    return {
        "followup_care_id": followup.followup_care_id,
        "pet_id": followup.pet_id,
        "pet_name": followup.pet.pet_name,
        "clinic_id": consultation.clinic_id,
        "clinic_name": consultation.clinic.clinic_name,
        "veterinarian_id": followup.veterinarian_id,
        "veterinarian_name": veterinarian.user.full_name,
        "recommended_date": followup.recommended_date,
        "existing_appointment_id": existing_id,
    }