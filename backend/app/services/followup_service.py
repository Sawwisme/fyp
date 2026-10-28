from datetime import datetime, timezone

from fastapi import HTTPException

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.clinic_time import CLINIC_TIMEZONE
from app.models import (
    Appointment,
    Consultation,
    FollowupCare,
    Pet,
    PetOwner,
    User,
)
from app.services.vet_profile_service import get_profile
from app.schemas.followups import FollowupReview, FollowupCancel
from app.services.return_visit_service import get_linked_visits


def list_my_followups(
    db: Session,
    current_user: User,
    search: str | None,
    status: str | None,
    offset: int,
    limit: int,
):
    veterinarian = get_profile(db, current_user)
    today = datetime.now(CLINIC_TIMEZONE).date()

    owner_name = func.coalesce(
        User.full_name,
        PetOwner.contact_name,
        "Not recorded",
    )

    statement = (
        select(
            FollowupCare,
            Pet.pet_name,
            owner_name.label("owner_name"),
        )
        .join(
            Consultation,
            Consultation.consultation_id
            == FollowupCare.consultation_id,
        )
        .join(Pet, Pet.pet_id == FollowupCare.pet_id)
        .join(
            Appointment,
            Appointment.appointment_id
            == Consultation.appointment_id,
        )
        .join(
            PetOwner,
            PetOwner.pet_owner_id == Appointment.pet_owner_id,
        )
        .outerjoin(User, User.user_id == PetOwner.user_id)
        .where(
            FollowupCare.veterinarian_id
            == veterinarian.veterinarian_id,
            Consultation.clinic_id == veterinarian.clinic_id,
            Consultation.status == "completed",
        )
    )

    if status:
        statement = statement.where(FollowupCare.status == status)

    if search and search.strip():
        term = search.strip().lower()

        statement = statement.where(
            or_(
                func.lower(Pet.pet_name).contains(
                    term, autoescape=True
                ),
                func.lower(owner_name).contains(
                    term, autoescape=True
                ),
            )
        )

    records = db.execute(
        statement
        .order_by(
            FollowupCare.recommended_date.is_(None),
            FollowupCare.recommended_date.asc(),
            FollowupCare.followup_care_id.asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    result = [
        {
            "followup_care_id": item.followup_care_id,
            "consultation_id": item.consultation_id,
            "pet_id": item.pet_id,
            "pet_name": pet_name,
            "owner_name": owner,
            "recommended_date": item.recommended_date,
            "followup_date": item.followup_date,
            "reason": item.reason,
            "care_instructions": item.care_instructions,
            "assessment_information": item.assessment_information,
            "notes": item.notes,
            "status": item.status,
            "photos_required": item.photos_required,
            "photo_instructions": item.photo_instructions,
            "visit_required": item.visit_required,
            "overdue": bool(
                item.status == "pending"
                and item.recommended_date
                and item.recommended_date < today
            ),
        }
        for item, pet_name, owner in records
    ]

    linked_visits = get_linked_visits(
        db,
        "followup",
        [item["followup_care_id"] for item in result],
        veterinarian,
    )

    for item in result:
        item["linked_visit"] = linked_visits.get(
            item["followup_care_id"]
        )

    return result

def _lock_pending_followup(
    db: Session,
    current_user: User,
    followup_id: int,
):
    veterinarian = get_profile(db, current_user)

    record = db.scalar(
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
            Consultation.clinic_id == veterinarian.clinic_id,
            Consultation.status == "completed",
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if record is None:
        raise HTTPException(
            404,
            "Follow-up not found in your assigned records.",
        )

    if record.status != "pending":
        raise HTTPException(
            409,
            "This follow-up is no longer pending. "
            "Refresh the list to view its current status.",
        )

    return record

def _reject_linked_appointment(
    db: Session,
    followup_id: int,
):
    appointment_id = db.scalar(
        select(Appointment.appointment_id)
        .where(
            Appointment.followup_care_id == followup_id,
            Appointment.status.notin_(["cancelled", "rejected"]),
        )
        .limit(1)
        .with_for_update()
    )

    if appointment_id is not None:
        raise HTTPException(
            409,
            f"This follow-up is linked to appointment "
            f"#{appointment_id}. Record the review through "
            "that appointment's consultation. To cancel the "
            "follow-up, cancel its linked appointment first.",
        )

def record_review(
    db: Session,
    current_user: User,
    followup_id: int,
    data: FollowupReview,
):
    try:
        record = _lock_pending_followup(
            db, current_user, followup_id
        )

        _reject_linked_appointment(
            db,
            followup_id,
        )

        record.assessment_information = (
            data.assessment_information
        )
        record.notes = data.notes
        record.followup_date = datetime.now(
            timezone.utc
        ).replace(tzinfo=None)
        record.status = "completed"

        result = {
            "followup_care_id": record.followup_care_id,
            "status": record.status,
            "followup_date": record.followup_date,
        }

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def cancel_followup(
    db: Session,
    current_user: User,
    followup_id: int,
    data: FollowupCancel,
):
    try:
        record = _lock_pending_followup(
            db, current_user, followup_id
        )

        _reject_linked_appointment(
            db,
            followup_id,
        )

        cancellation_note = f"Cancellation reason: {data.reason}"

        record.notes = (
            f"{record.notes}\n\n{cancellation_note}"
            if record.notes
            else cancellation_note
        )
        record.status = "cancelled"

        result = {
            "followup_care_id": record.followup_care_id,
            "status": record.status,
            "followup_date": record.followup_date,
        }

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise