from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Appointment, PetOwner, Schedule, TimeSlot
from app.services.vet_profile_service import get_profile


def list_my_appointments(
    db: Session,
    current_user,
    appointment_date: date,
    offset: int,
    limit: int,
):
    
    veterinarian = get_profile(db, current_user)

    records = db.scalars(
        select(Appointment)
        .join(
            TimeSlot,
            TimeSlot.time_slot_id == Appointment.time_slot_id,
        )
        .join(
            Schedule,
            Schedule.schedule_id == TimeSlot.schedule_id,
        )
        .where(
            Appointment.veterinarian_id
            == veterinarian.veterinarian_id,
            Schedule.veterinarian_id
            == veterinarian.veterinarian_id,
            Schedule.schedule_date == appointment_date,
        )
        .options(
            selectinload(Appointment.pet),
            selectinload(Appointment.owner)
            .selectinload(PetOwner.user),
            selectinload(Appointment.time_slot),
        )
        .order_by(
            TimeSlot.start_time,
            Appointment.appointment_id,
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return [
        {
            "appointment_id": record.appointment_id,
            "appointment_date": appointment_date,
            "start_time": record.time_slot.start_time,
            "end_time": record.time_slot.end_time,
            "pet_id": record.pet_id,
            "pet_name": record.pet.pet_name,
            "time_slot_id": record.time_slot_id,
            "owner_name": (
                record.owner.user.full_name
                if record.owner.user is not None
                else record.owner.contact_name or "Not recorded"
            ),
            "appointment_type": record.appointment_type,
            "appointment_source": record.appointment_source,
            "status": record.status,
        }
        for record in records
    ]

def get_my_calendar(
    db: Session,
    current_user,
    start_date: date,
    end_date: date,
):
    veterinarian = get_profile(db, current_user)

    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="End date must not be before start date.",
        )

    if (end_date - start_date).days >= 42:
        raise HTTPException(
            status_code=400,
            detail="Choose a maximum of 42 calendar days.",
        )

    # Count appointments separately to avoid counting empty slots.
    counts = (
        select(
            TimeSlot.schedule_id,
            func.count(Appointment.appointment_id).label(
                "appointment_count"
            ),
        )
        .join(
            Appointment,
            Appointment.time_slot_id == TimeSlot.time_slot_id,
        )
        .where(
            Appointment.veterinarian_id
            == veterinarian.veterinarian_id,
            Appointment.status.notin_(["cancelled", "rejected"]),
        )
        .group_by(TimeSlot.schedule_id)
        .subquery()
    )

    records = db.execute(
        select(
            Schedule.schedule_id,
            Schedule.schedule_date,
            Schedule.start_time,
            Schedule.end_time,
            func.coalesce(
                counts.c.appointment_count, 0
            ).label("appointment_count"),
        )
        .outerjoin(
            counts,
            counts.c.schedule_id == Schedule.schedule_id,
        )
        .where(
            Schedule.veterinarian_id
            == veterinarian.veterinarian_id,
            Schedule.status == "active",
            Schedule.schedule_date >= start_date,
            Schedule.schedule_date <= end_date,
        )
        .order_by(
            Schedule.schedule_date,
            Schedule.start_time,
            Schedule.schedule_id,
        )
    ).mappings().all()

    return [dict(record) for record in records]