from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    Clinic,
    Schedule,
    TimeSlot,
    User,
    Veterinarian,
)


CLINIC_TIMEZONE = timezone(timedelta(hours=8))


def eligible_veterinarians():
    return (
        select(
            Veterinarian.veterinarian_id,
            User.full_name,
            Clinic.clinic_id,
            Clinic.clinic_name,
            Veterinarian.specialization,
        )
        .join(User, Veterinarian.user_id == User.user_id)
        .join(Clinic, Veterinarian.clinic_id == Clinic.clinic_id)
        .where(
            User.role == "veterinarian",
            User.status == "active",
            Veterinarian.approval_status == "approved",
            Clinic.status == "active",
        )
    )


def list_veterinarians(
    db: Session,
    offset: int,
    limit: int,
):
    query = (
        eligible_veterinarians()
        .order_by(User.full_name, Veterinarian.veterinarian_id)
        .offset(offset)
        .limit(limit)
    )

    return db.execute(query).mappings().all()


def list_available_slots(
    db: Session,
    veterinarian_id: int,
    appointment_date: date,
    offset: int,
    limit: int,
):
    now = datetime.now(CLINIC_TIMEZONE)

    if appointment_date < now.date():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose today or a future date.",
        )

    veterinarian = db.execute(
        eligible_veterinarians().where(
            Veterinarian.veterinarian_id == veterinarian_id
        )
    ).first()

    if veterinarian is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veterinarian is not available for booking.",
        )

    occupied = exists().where(
        Appointment.time_slot_id == TimeSlot.time_slot_id,
        Appointment.status.notin_(["cancelled", "rejected"]),
    )

    query = (
        select(
            TimeSlot.time_slot_id,
            Schedule.schedule_id,
            Veterinarian.veterinarian_id,
            User.full_name.label("veterinarian_name"),
            Clinic.clinic_id,
            Clinic.clinic_name,
            Schedule.schedule_date,
            TimeSlot.start_time,
            TimeSlot.end_time,
        )
        .join(Schedule, TimeSlot.schedule_id == Schedule.schedule_id)
        .join(
            Veterinarian,
            Schedule.veterinarian_id == Veterinarian.veterinarian_id,
        )
        .join(User, Veterinarian.user_id == User.user_id)
        .join(Clinic, Veterinarian.clinic_id == Clinic.clinic_id)
        .where(
            Clinic.status == "active",
            Veterinarian.veterinarian_id == veterinarian_id,
            Veterinarian.approval_status == "approved",
            User.role == "veterinarian",
            User.status == "active",
            Schedule.schedule_date == appointment_date,
            Schedule.status == "active",
            TimeSlot.status == "available",
            TimeSlot.end_time > TimeSlot.start_time,
            TimeSlot.start_time >= Schedule.start_time,
            TimeSlot.end_time <= Schedule.end_time,
            ~occupied,
        )
    )

    if appointment_date == now.date():
        query = query.where(
            TimeSlot.start_time > now.time().replace(tzinfo=None)
        )

    query = (
        query
        .order_by(TimeSlot.start_time, TimeSlot.time_slot_id)
        .offset(offset)
        .limit(limit)
    )

    return db.execute(query).mappings().all()