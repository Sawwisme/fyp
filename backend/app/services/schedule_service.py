from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Appointment, Schedule, TimeSlot, User, Veterinarian
from app.schemas.schedule import ScheduleCreate
from app.services.admin_profile_service import get_admin_record
from app.services.availability_service import CLINIC_TIMEZONE


def serialize_schedule(schedule: Schedule) -> dict:
    return {
        "schedule_id": schedule.schedule_id,
        "veterinarian_id": schedule.veterinarian_id,
        "schedule_date": schedule.schedule_date,
        "start_time": schedule.start_time,
        "end_time": schedule.end_time,
        "status": schedule.status,
        "time_slots": sorted(
            schedule.time_slots,
            key=lambda slot: (slot.start_time, slot.time_slot_id),
        ),
    }


def create_schedule(
    db: Session,
    current_user: User,
    data: ScheduleCreate,
) -> dict:
    get_admin_record(db, current_user)

    try:
        # Serialize schedule creation for this veterinarian.
        veterinarian = db.scalar(
            select(Veterinarian)
            .join(Veterinarian.user)
            .where(
                Veterinarian.veterinarian_id == data.veterinarian_id,
                Veterinarian.approval_status == "approved",
                User.role == "veterinarian",
                User.status == "active",
            )
            .with_for_update()
        )

        if veterinarian is None:
            raise HTTPException(
                status_code=404,
                detail="An active, approved veterinarian was not found.",
            )

        start = datetime.combine(
            data.schedule_date,
            data.start_time,
            tzinfo=CLINIC_TIMEZONE,
        )
        end = datetime.combine(
            data.schedule_date,
            data.end_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        if start <= datetime.now(CLINIC_TIMEZONE):
            raise HTTPException(
                status_code=400,
                detail="The schedule must start in the future.",
            )

        overlapping = db.scalar(
            select(Schedule.schedule_id)
            .where(
                Schedule.veterinarian_id == data.veterinarian_id,
                Schedule.schedule_date == data.schedule_date,
                Schedule.status == "active",
                Schedule.start_time < data.end_time,
                Schedule.end_time > data.start_time,
            )
            .limit(1)
            .with_for_update()
        )

        if overlapping is not None:
            raise HTTPException(
                status_code=409,
                detail="This overlaps an existing active schedule.",
            )

        schedule = Schedule(
            veterinarian_id=data.veterinarian_id,
            schedule_date=data.schedule_date,
            start_time=data.start_time,
            end_time=data.end_time,
            status="active",
        )

        cursor = start
        step = timedelta(minutes=data.slot_minutes)

        while cursor < end:
            slot_end = cursor + step

            schedule.time_slots.append(
                TimeSlot(
                    start_time=cursor.time(),
                    end_time=slot_end.time(),
                    status="available",
                )
            )

            cursor = slot_end

        db.add(schedule)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(schedule)

    return serialize_schedule(schedule)


def list_schedules(
    db: Session,
    current_user: User,
    veterinarian_id: int | None,
    schedule_date: date | None,
    offset: int,
    limit: int,
) -> list[dict]:
    get_admin_record(db, current_user)

    statement = select(Schedule).options(
        selectinload(Schedule.time_slots)
    )

    if veterinarian_id is not None:
        statement = statement.where(
            Schedule.veterinarian_id == veterinarian_id
        )

    if schedule_date is not None:
        statement = statement.where(
            Schedule.schedule_date == schedule_date
        )

    statement = (
        statement
        .order_by(
            Schedule.schedule_date,
            Schedule.start_time,
            Schedule.schedule_id,
        )
        .offset(offset)
        .limit(limit)
    )

    return [
        serialize_schedule(schedule)
        for schedule in db.scalars(statement).all()
    ]

def lock_schedule(db: Session, schedule_id: int) -> Schedule:
    veterinarian_id = db.scalar(
        select(Schedule.veterinarian_id).where(
            Schedule.schedule_id == schedule_id
        )
    )

    if veterinarian_id is None:
        raise HTTPException(
            status_code=404,
            detail="Schedule not found.",
        )

    # Keep the same locking order as schedule creation.
    db.scalar(
        select(Veterinarian)
        .where(Veterinarian.veterinarian_id == veterinarian_id)
        .with_for_update()
    )

    schedule = db.scalar(
        select(Schedule)
        .where(Schedule.schedule_id == schedule_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found.")

    return schedule


def reject_occupied_slots(db: Session, slot_ids: list[int]) -> None:
    if not slot_ids:
        return

    appointment_id = db.scalar(
        select(Appointment.appointment_id)
        .where(
            Appointment.time_slot_id.in_(slot_ids),
            Appointment.status.notin_(["cancelled", "rejected"]),
        )
        .limit(1)
        .with_for_update()
    )

    if appointment_id is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "An appointment uses this schedule or slot. "
                "Handle the appointment before changing availability."
            ),
        )


def cancel_schedule(
    db: Session,
    current_user: User,
    schedule_id: int,
) -> dict:
    get_admin_record(db, current_user)

    try:
        schedule = lock_schedule(db, schedule_id)

        if schedule.status == "cancelled":
            result = serialize_schedule(schedule)
            db.rollback()
            return result

        if schedule.status != "active":
            raise HTTPException(
                status_code=409,
                detail="Only active schedules can be cancelled.",
            )

        start = datetime.combine(
            schedule.schedule_date,
            schedule.start_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        if start <= datetime.now(CLINIC_TIMEZONE):
            raise HTTPException(
                status_code=409,
                detail="A schedule that has already started cannot be cancelled.",
            )

        slots = list(
            db.scalars(
                select(TimeSlot)
                .where(TimeSlot.schedule_id == schedule_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            ).all()
        )

        reject_occupied_slots(
            db,
            [slot.time_slot_id for slot in slots],
        )

        schedule.status = "cancelled"

        for slot in slots:
            slot.status = "blocked"

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(schedule)
    return serialize_schedule(schedule)


def update_slot_status(
    db: Session,
    current_user: User,
    schedule_id: int,
    slot_id: int,
    new_status: str,
) -> dict:
    if current_user.role == "clinic_administrator":
        get_admin_record(db, current_user)
    elif current_user.role != "veterinarian":
        raise HTTPException(
            status_code=403,
            detail="You cannot manage slot availability.",
        )

    try:
        schedule = lock_schedule(db, schedule_id)

        if current_user.role == "veterinarian":
            own_veterinarian_id = db.scalar(
                select(Veterinarian.veterinarian_id)
                .where(
                    Veterinarian.veterinarian_id
                    == schedule.veterinarian_id,
                    Veterinarian.user_id == current_user.user_id,
                    Veterinarian.approval_status == "approved",
                )
                .with_for_update()
            )

            if own_veterinarian_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="You can only manage your own approved schedule.",
                )

        if schedule.status != "active":
            raise HTTPException(
                status_code=409,
                detail="Slots can only be changed within an active schedule.",
            )

        slot = db.scalar(
            select(TimeSlot)
            .where(
                TimeSlot.time_slot_id == slot_id,
                TimeSlot.schedule_id == schedule_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if slot is None:
            raise HTTPException(
                status_code=404,
                detail="Slot not found in this schedule.",
            )

        start = datetime.combine(
            schedule.schedule_date,
            slot.start_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        if start <= datetime.now(CLINIC_TIMEZONE):
            raise HTTPException(
                status_code=409,
                detail="A slot that has already started cannot be changed.",
            )

        reject_occupied_slots(db, [slot_id])

        slot.status = new_status
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(schedule)
    return serialize_schedule(schedule)