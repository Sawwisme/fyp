from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinic_time import CLINIC_TIMEZONE
from app.models import (
    Appointment,
    Clinic,
    Pet,
    PetOwner,
    Schedule,
    TimeSlot,
    User,
    Veterinarian,
)
from app.schemas.clinic_appointments import ClinicAppointmentCreate
from app.services.admin_profile_service import get_admin_record
from app.services.clinic_customer_service import customer_statement
from app.services.schedule_service import (
    lock_schedule,
    reject_occupied_slots,
)


def create_appointment(
    db: Session,
    current_user: User,
    data: ClinicAppointmentCreate,
):
    try:
        administrator = get_admin_record(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == administrator.clinic_id,
                Clinic.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(
                status_code=403,
                detail="Your clinic is not active.",
            )

        schedule_id = db.scalar(
            select(TimeSlot.schedule_id).where(
                TimeSlot.time_slot_id == data.time_slot_id
            )
        )

        if schedule_id is None:
            raise HTTPException(
                status_code=404,
                detail="Appointment slot not found.",
            )

        # Checks clinic access and locks the vet and schedule.
        schedule = lock_schedule(
            db,
            schedule_id,
            current_user,
        )

        eligible_vet = db.scalar(
            select(Veterinarian.veterinarian_id)
            .join(Veterinarian.user)
            .where(
                Veterinarian.veterinarian_id
                == schedule.veterinarian_id,
                Veterinarian.clinic_id == clinic.clinic_id,
                Veterinarian.approval_status == "approved",
                User.role == "veterinarian",
                User.status == "active",
            )
            .with_for_update()
        )

        if eligible_vet is None:
            raise HTTPException(
                status_code=409,
                detail="This veterinarian is unavailable.",
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

        if (
            slot is None
            or schedule.status != "active"
            or slot.status != "available"
        ):
            raise HTTPException(
                status_code=409,
                detail="This slot is no longer available.",
            )

        now = datetime.now(CLINIC_TIMEZONE)

        start = datetime.combine(
            schedule.schedule_date,
            slot.start_time,
            tzinfo=CLINIC_TIMEZONE,
        )
        end = datetime.combine(
            schedule.schedule_date,
            slot.end_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        if end <= now:
            raise HTTPException(
                status_code=400,
                detail="This slot has already ended.",
            )

        if data.appointment_source == "walk_in":
            if schedule.schedule_date != now.date():
                raise HTTPException(
                    status_code=400,
                    detail="Walk-in appointments must be for today.",
                )
        elif start <= now:
            raise HTTPException(
                status_code=400,
                detail="Reception bookings must use a future slot.",
            )

        # A claimed slot cannot be booked again, even if its
        # status was accidentally left as available.
        reject_occupied_slots(db, [slot.time_slot_id])

        owner = db.scalar(
            customer_statement(clinic.clinic_id)
            .where(
                PetOwner.pet_owner_id == data.pet_owner_id
            )
        )

        if owner is None:
            raise HTTPException(
                status_code=404,
                detail="Customer not found in your clinic.",
            )

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
                status_code=400,
                detail="Select a pet belonging to this customer.",
            )

        # Locking the pet also serializes booking attempts for
        # the same pet into different slots.
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
                status_code=409,
                detail="This pet already has an overlapping appointment.",
            )

        appointment = Appointment(
            pet_owner_id=owner.pet_owner_id,
            pet_id=pet.pet_id,
            veterinarian_id=schedule.veterinarian_id,
            time_slot_id=slot.time_slot_id,
            appointment_type=data.appointment_type,
            appointment_source=data.appointment_source,
            appointment_date=schedule.schedule_date,
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