from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinic_time import CLINIC_TIMEZONE
from app.models import (
    Appointment,
    Clinic,
    Pet,
    Schedule,
    TimeSlot,
    User,
    Veterinarian,
)
from app.schemas.owner_appointments import OwnerAppointmentCreate
from app.services.pet_service import get_owner_profile
from app.services.schedule_service import reject_occupied_slots


def create_appointment(
    db: Session,
    current_user: User,
    data: OwnerAppointmentCreate,
):
    try:
        owner = get_owner_profile(db, current_user)

        location = db.execute(
            select(
                TimeSlot.schedule_id,
                Schedule.veterinarian_id,
                Veterinarian.clinic_id,
            )
            .join(
                Schedule,
                Schedule.schedule_id == TimeSlot.schedule_id,
            )
            .join(
                Veterinarian,
                Veterinarian.veterinarian_id
                == Schedule.veterinarian_id,
            )
            .where(TimeSlot.time_slot_id == data.time_slot_id)
        ).first()

        if location is None:
            raise HTTPException(404, "Appointment slot not found.")

        # Follow the same lock order as staff booking:
        # clinic -> vet -> schedule -> slot -> pet.
        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == location.clinic_id,
                Clinic.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(
                409, "This clinic is unavailable for booking."
            )

        veterinarian = db.scalar(
            select(Veterinarian)
            .join(Veterinarian.user)
            .where(
                Veterinarian.veterinarian_id
                == location.veterinarian_id,
                Veterinarian.clinic_id == clinic.clinic_id,
                Veterinarian.approval_status == "approved",
                User.role == "veterinarian",
                User.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if veterinarian is None:
            raise HTTPException(
                409, "This veterinarian is unavailable for booking."
            )

        schedule = db.scalar(
            select(Schedule)
            .where(
                Schedule.schedule_id == location.schedule_id,
                Schedule.veterinarian_id
                == veterinarian.veterinarian_id,
                Schedule.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if schedule is None:
            raise HTTPException(
                409, "This schedule is no longer available."
            )

        slot = db.scalar(
            select(TimeSlot)
            .where(
                TimeSlot.time_slot_id == data.time_slot_id,
                TimeSlot.schedule_id == schedule.schedule_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if slot is None or slot.status != "available":
            raise HTTPException(
                409, "This slot is no longer available."
            )

        if (
            slot.end_time <= slot.start_time
            or slot.start_time < schedule.start_time
            or slot.end_time > schedule.end_time
        ):
            raise HTTPException(
                409, "This slot has invalid working hours."
            )

        start = datetime.combine(
            schedule.schedule_date,
            slot.start_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        if start <= datetime.now(CLINIC_TIMEZONE):
            raise HTTPException(
                400, "Choose a future appointment slot."
            )

        reject_occupied_slots(db, [slot.time_slot_id])

        pet = db.scalar(
            select(Pet)
            .where(
                Pet.pet_id == data.pet_id,
                Pet.pet_owner_id == owner.pet_owner_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if pet is None:
            raise HTTPException(
                404, "Pet not found in your account."
            )

        overlapping = db.scalar(
            select(Appointment.appointment_id)
            .join(
                TimeSlot,
                TimeSlot.time_slot_id == Appointment.time_slot_id,
            )
            .join(
                Schedule,
                Schedule.schedule_id == TimeSlot.schedule_id,
            )
            .where(
                Appointment.pet_id == pet.pet_id,
                Appointment.status.notin_(["cancelled", "rejected"]),
                Schedule.schedule_date == schedule.schedule_date,
                TimeSlot.start_time < slot.end_time,
                TimeSlot.end_time > slot.start_time,
            )
            .limit(1)
            .with_for_update()
        )

        if overlapping is not None:
            raise HTTPException(
                409,
                "Your pet already has an overlapping appointment.",
            )

        appointment = Appointment(
            pet_owner_id=owner.pet_owner_id,
            pet_id=pet.pet_id,
            veterinarian_id=veterinarian.veterinarian_id,
            time_slot_id=slot.time_slot_id,
            appointment_date=schedule.schedule_date,
            appointment_type=data.appointment_type,
            appointment_source="owner_app",
            created_by_user_id=current_user.user_id,
            status="confirmed",
        )

        slot.status = "booked"
        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        return appointment

    except Exception:
        db.rollback()
        raise