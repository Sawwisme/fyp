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
    Consultation,
    FollowupCare,
    Treatment,
    TreatmentProgress,
)
from app.schemas.clinic_appointments import ClinicAppointmentCreate
from app.services.admin_profile_service import get_admin_record
from app.services.clinic_customer_service import customer_statement
from app.services.schedule_service import (
    lock_schedule,
    reject_occupied_slots,
)
from app.services.vet_absence_service import reject_absent_slots

from app.services.vet_profile_service import get_profile

def _validate_return_visit(
    db: Session,
    clinic_id: int,
    data: ClinicAppointmentCreate,
):
    if data.planned_treatment_id is not None:
        source = db.execute(
            select(
                TreatmentProgress,
                Consultation,
                Appointment,
            )
            .join(
                Treatment,
                Treatment.treatment_id
                == TreatmentProgress.treatment_id,
            )
            .join(
                Consultation,
                Consultation.consultation_id
                == Treatment.consultation_id,
            )
            .join(
                Appointment,
                Appointment.appointment_id
                == Consultation.appointment_id,
            )
            .where(
                TreatmentProgress.treatment_id
                == data.planned_treatment_id,
                Treatment.status == "planned",
                Consultation.clinic_id == clinic_id,
                Consultation.status == "completed",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        ).first()

        link_column = Appointment.planned_treatment_id
        link_id = data.planned_treatment_id

        if source is None:
            raise HTTPException(404, "Treatment plan not found.")

        task, consultation, original_appointment = source

        if task.status not in ("planned", "in_progress"):
            raise HTTPException(
                409, "This treatment plan is no longer open."
            )

        expected_vet = consultation.veterinarian_id

    elif data.followup_care_id is not None:
        source = db.execute(
            select(
                FollowupCare,
                Consultation,
                Appointment,
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
            .where(
                FollowupCare.followup_care_id
                == data.followup_care_id,
                Consultation.clinic_id == clinic_id,
                Consultation.status == "completed",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        ).first()

        link_column = Appointment.followup_care_id
        link_id = data.followup_care_id

        if source is None:
            raise HTTPException(404, "Follow-up task not found.")

        task, consultation, original_appointment = source

        if task.status != "pending":
            raise HTTPException(
                409, "This follow-up task is no longer pending."
            )

        expected_vet = task.veterinarian_id

    else:
        return None

    if (
        data.pet_id != consultation.pet_id
        or data.pet_owner_id != original_appointment.pet_owner_id
    ):
        raise HTTPException(
            400,
            "The return visit must use the original patient and owner.",
        )

    existing = db.scalar(
        select(Appointment.appointment_id)
        .where(
            link_column == link_id,
            Appointment.status.notin_(["cancelled", "rejected"]),
        )
        .limit(1)
        .with_for_update()
    )

    if existing is not None:
        raise HTTPException(
            409,
            "This plan already has a linked appointment. "
            "Manage that appointment before booking another.",
        )

    return expected_vet

def create_appointment(
    db: Session,
    current_user: User,
    data: ClinicAppointmentCreate,
):
    try:
        if current_user.role == "clinic_administrator":
            profile = get_admin_record(db, current_user)

        elif current_user.role == "veterinarian":
            if (
                data.planned_treatment_id is None
                and data.followup_care_id is None
            ):
                raise HTTPException(
                    403,
                    "Veterinarians can book linked return visits only.",
                )

            if data.appointment_source != "reception":
                raise HTTPException(
                    400,
                    "Return visits must use a future appointment slot.",
                )

            profile = get_profile(db, current_user)

        else:
            raise HTTPException(
                403,
                "You cannot create clinic appointments.",
            )

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == profile.clinic_id,
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

        return_visit_vet_id = _validate_return_visit(
            db,
            clinic.clinic_id,
            data,
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

        if (
            return_visit_vet_id is not None
            and schedule.veterinarian_id != return_visit_vet_id
        ):
            raise HTTPException(
                400,
                "Select a slot belonging to the vet "
                "responsible for this treatment or follow-up.",
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
        reject_absent_slots(db, [slot.time_slot_id])
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
            planned_treatment_id=data.planned_treatment_id,
            followup_care_id=data.followup_care_id,
        )

        slot.status = "booked"

        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        return appointment

    except Exception:
        db.rollback()
        raise

def cancel_appointment(
    db: Session,
    current_user: User,
    appointment_id: int,
):
    try:
        administrator = get_admin_record(db, current_user)

        # Use the same lock order as appointment creation.
        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == administrator.clinic_id,
                Clinic.status == "active",
            )
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(
                status_code=403,
                detail="Your clinic is not active.",
            )

        location = db.execute(
            select(
                TimeSlot.schedule_id,
                TimeSlot.time_slot_id,
            )
            .join(
                Appointment,
                Appointment.time_slot_id == TimeSlot.time_slot_id,
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
            .where(
                Appointment.appointment_id == appointment_id,
                Veterinarian.clinic_id == clinic.clinic_id,
            )
        ).first()

        if location is None:
            raise HTTPException(
                status_code=404,
                detail="Appointment not found in your clinic.",
            )

        schedule = lock_schedule(
            db,
            location.schedule_id,
            current_user,
        )

        slot = db.scalar(
            select(TimeSlot)
            .where(
                TimeSlot.time_slot_id == location.time_slot_id
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        appointment = db.scalar(
            select(Appointment)
            .where(
                Appointment.appointment_id == appointment_id,
                Appointment.time_slot_id == slot.time_slot_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if appointment is None:
            raise HTTPException(
                status_code=409,
                detail="Appointment changed. Refresh and try again.",
            )

        if appointment.status == "cancelled":
            return {"message": "Appointment is already cancelled."}

        if appointment.status not in ("pending", "confirmed"):
            raise HTTPException(
                status_code=409,
                detail="Only pending or confirmed appointments can be cancelled.",
            )

        start = datetime.combine(
            schedule.schedule_date,
            slot.start_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        if start <= datetime.now(CLINIC_TIMEZONE):
            raise HTTPException(
                status_code=409,
                detail="An appointment that has started cannot be cancelled.",
            )

        appointment.status = "cancelled"
        db.flush()

        # Keep the slot unavailable if another appointment occupies it.
        occupied = db.scalar(
            select(Appointment.appointment_id)
            .where(
                Appointment.time_slot_id == slot.time_slot_id,
                Appointment.status.notin_(["cancelled", "rejected"]),
            )
            .limit(1)
            .with_for_update()
        )

        if (
            occupied is None
            and schedule.status == "active"
            and slot.status == "booked"
        ):
            slot.status = "available"

        db.commit()

        return {"message": "Appointment cancelled successfully."}

    except Exception:
        db.rollback()
        raise

def reschedule_appointment(
    db: Session,
    current_user: User,
    appointment_id: int,
    new_slot_id: int,
):
    try:
        administrator = get_admin_record(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == administrator.clinic_id,
                Clinic.status == "active",
            )
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(403, "Your clinic is not active.")

        # Resolve the current booking within this clinic.
        current = db.execute(
            select(
                Appointment.time_slot_id,
                TimeSlot.schedule_id,
            )
            .join(
                TimeSlot,
                TimeSlot.time_slot_id == Appointment.time_slot_id,
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
            .where(
                Appointment.appointment_id == appointment_id,
                Veterinarian.clinic_id == clinic.clinic_id,
            )
        ).first()

        if current is None:
            raise HTTPException(
                404, "Appointment not found in your clinic."
            )

        if current.time_slot_id == new_slot_id:
            raise HTTPException(
                400, "Choose a different appointment slot."
            )

        target_schedule_id = db.scalar(
            select(TimeSlot.schedule_id).where(
                TimeSlot.time_slot_id == new_slot_id
            )
        )

        if target_schedule_id is None:
            raise HTTPException(404, "New slot not found.")

        # Lock both schedules before changing either booking.
        schedules = {}

        for schedule_id in sorted({
            current.schedule_id,
            target_schedule_id,
        }):
            schedules[schedule_id] = lock_schedule(
                db, schedule_id, current_user
            )

        slots = {
            slot.time_slot_id: slot
            for slot in db.scalars(
                select(TimeSlot)
                .where(
                    TimeSlot.time_slot_id.in_([
                        current.time_slot_id,
                        new_slot_id,
                    ])
                )
                .order_by(TimeSlot.time_slot_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            ).all()
        }

        old_slot = slots.get(current.time_slot_id)
        new_slot = slots.get(new_slot_id)

        if old_slot is None or new_slot is None:
            raise HTTPException(
                409, "A slot changed. Refresh and try again."
            )

        appointment = db.scalar(
            select(Appointment)
            .where(
                Appointment.appointment_id == appointment_id
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if (
            appointment is None
            or appointment.time_slot_id != old_slot.time_slot_id
        ):
            raise HTTPException(
                409, "Appointment changed. Refresh and try again."
            )

        if appointment.status not in ("pending", "confirmed"):
            raise HTTPException(
                409,
                "Only pending or confirmed appointments can be rescheduled.",
            )

        old_schedule = schedules[current.schedule_id]
        new_schedule = schedules[target_schedule_id]
        now = datetime.now(CLINIC_TIMEZONE)

        old_start = datetime.combine(
            old_schedule.schedule_date,
            old_slot.start_time,
            tzinfo=CLINIC_TIMEZONE,
        )
        new_start = datetime.combine(
            new_schedule.schedule_date,
            new_slot.start_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        if old_start <= now:
            raise HTTPException(
                409,
                "An appointment that has started cannot be rescheduled.",
            )

        if new_start <= now:
            raise HTTPException(
                400, "Choose a future appointment slot."
            )

        if (
            new_schedule.status != "active"
            or new_slot.status != "available"
        ):
            raise HTTPException(
                409, "The new slot is no longer available."
            )

        eligible_vet = db.scalar(
            select(Veterinarian.veterinarian_id)
            .join(Veterinarian.user)
            .where(
                Veterinarian.veterinarian_id
                == new_schedule.veterinarian_id,
                Veterinarian.clinic_id == clinic.clinic_id,
                Veterinarian.approval_status == "approved",
                User.role == "veterinarian",
                User.status == "active",
            )
            .with_for_update()
        )

        if eligible_vet is None:
            raise HTTPException(
                409, "The selected veterinarian is unavailable."
            )
        reject_absent_slots(db, [new_slot.time_slot_id])
        reject_occupied_slots(db, [new_slot.time_slot_id])

        pet = db.scalar(
            select(Pet)
            .where(Pet.pet_id == appointment.pet_id)
            .with_for_update()
        )

        if pet is None:
            raise HTTPException(404, "Pet not found.")

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
                Appointment.pet_id == appointment.pet_id,
                Appointment.appointment_id != appointment_id,
                Appointment.status.notin_(["cancelled", "rejected"]),
                Schedule.schedule_date == new_schedule.schedule_date,
                TimeSlot.start_time < new_slot.end_time,
                TimeSlot.end_time > new_slot.start_time,
            )
            .limit(1)
            .with_for_update()
        )

        if overlapping is not None:
            raise HTTPException(
                409,
                "This pet already has an overlapping appointment.",
            )

        appointment.time_slot_id = new_slot.time_slot_id
        appointment.veterinarian_id = new_schedule.veterinarian_id
        appointment.appointment_date = new_schedule.schedule_date

        new_slot.status = "booked"
        db.flush()

        # Release the previous slot only if nobody else occupies it.
        occupied = db.scalar(
            select(Appointment.appointment_id)
            .where(
                Appointment.time_slot_id == old_slot.time_slot_id,
                Appointment.status.notin_(["cancelled", "rejected"]),
            )
            .limit(1)
            .with_for_update()
        )

        if (
            occupied is None
            and old_schedule.status == "active"
            and old_slot.status == "booked"
        ):
            old_slot.status = "available"

        db.commit()

        return {"message": "Appointment rescheduled successfully."}

    except Exception:
        db.rollback()
        raise