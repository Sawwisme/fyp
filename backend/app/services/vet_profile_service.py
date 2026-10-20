from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, Veterinarian, Clinic
from app.schemas.vet_profile import VetProfileUpdate

from datetime import date

from sqlalchemy.orm import selectinload

from app.models import Schedule
from app.services.schedule_service import serialize_schedule


def get_profile(
    db: Session,
    current_user: User,
) -> Veterinarian:
    veterinarian = db.scalar(
        select(Veterinarian)
        .join(Veterinarian.clinic)
        .where(
            Veterinarian.user_id == current_user.user_id,
            Clinic.status == "active",
        )
    )

    if veterinarian is None:
        raise HTTPException(
            status_code=403,
            detail="This account has no veterinarian profile.",
        )

    if veterinarian.approval_status != "approved":
        raise HTTPException(
            status_code=403,
            detail="This veterinarian account is not approved.",
        )

    return veterinarian


def update_profile(
    db: Session,
    current_user: User,
    data: VetProfileUpdate,
) -> Veterinarian:
    veterinarian = get_profile(db, current_user)
    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update.",
        )

    if "full_name" in changes:
        current_user.full_name = changes["full_name"]

    if "phone_number" in changes:
        current_user.phone_number = changes["phone_number"]

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(current_user)
    db.refresh(veterinarian)

    return veterinarian

def list_my_schedules(
    db: Session,
    current_user: User,
    schedule_date: date,
    offset: int,
    limit: int,
) -> list[dict]:
    veterinarian = get_profile(db, current_user)

    statement = (
        select(Schedule)
        .options(selectinload(Schedule.time_slots))
        .where(
            Schedule.veterinarian_id == veterinarian.veterinarian_id,
            Schedule.schedule_date == schedule_date,
        )
        .order_by(Schedule.start_time, Schedule.schedule_id)
        .offset(offset)
        .limit(limit)
    )

    return [
        serialize_schedule(schedule)
        for schedule in db.scalars(statement).all()
    ]