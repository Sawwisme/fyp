from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session
from app.services.ai_scan_booking_service import validate_scan_booking

from app.clinic_time import CLINIC_TIMEZONE
from app.models import (
    Appointment,
    Clinic,
    Pet,
    Schedule,
    TimeSlot,
    User,
    Veterinarian,
    Consultation,
    FollowupCare,
)
from app.schemas.owner_appointments import OwnerAppointmentCreate
from app.services.pet_service import get_owner_profile
from app.services.schedule_service import reject_occupied_slots
from app.services.vet_absence_service import reject_absent_slots, get_rearrangement_ids

from app.services.booking_deposit_service import (
    prepare_booking_request,
    prepare_deposit_payment,
)

from app.services.booking_refund_request_service import (
    queue_booking_deposit_refund,
)

from app.services.ai_review_booking_service import (
    validate_review_booking,
)

def create_appointment(
    db: Session,
    current_user: User,
    data: OwnerAppointmentCreate,
):
    try:
        owner = get_owner_profile(db, current_user)

        if data.ai_analysis_id is not None:
            if not data.share_ai_assessment:
                raise HTTPException(
                    422,
                    "Confirm sharing this assessment with the "
                    "selected clinic before booking.",
                )

            if (
                data.followup_care_id is not None
                or data.ai_assessment_review_id is not None
            ):
                raise HTTPException(
                    422,
                    "Choose one assessment or follow-up booking context.",
                )

        elif data.share_ai_assessment:
            raise HTTPException(
                422,
                "Choose an assessment before confirming sharing.",
            )

        if (
            data.ai_assessment_review_id is not None
            and data.followup_care_id is not None
        ):
            raise HTTPException(
                422,
                "Choose either an assessment review or a follow-up "
                "as the booking context.",
            )

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

        existing = prepare_booking_request(
            db,
            owner,
            clinic,
            data,
        )

        if existing is not None:
            db.commit()
            db.refresh(existing)
            return existing

        if data.followup_care_id is not None:
            if data.appointment_type != "follow_up":
                raise HTTPException(
                    422,
                    "A linked follow-up booking must use follow_up type.",
                )

            followup = db.scalar(
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
                .join(
                    Pet,
                    Pet.pet_id == FollowupCare.pet_id,
                )
                .where(
                    FollowupCare.followup_care_id == data.followup_care_id,
                    FollowupCare.pet_id == data.pet_id,
                    FollowupCare.pet_id == Consultation.pet_id,
                    Consultation.clinic_id == clinic.clinic_id,
                    Consultation.status == "completed",
                    Appointment.pet_owner_id == owner.pet_owner_id,
                    Pet.pet_owner_id == owner.pet_owner_id,
                )
                .execution_options(populate_existing=True)
                .with_for_update()
            )

            if followup is None:
                raise HTTPException(
                    404,
                    "Follow-up not found for this pet and clinic.",
                )

            if followup.status != "pending":
                raise HTTPException(
                    409,
                    "This follow-up is already closed.",
                )

            if not followup.visit_required:
                raise HTTPException(
                    409,
                    "Your veterinarian has not requested an in-clinic review.",
                )

            if followup.veterinarian_id != location.veterinarian_id:
                raise HTTPException(
                    422,
                    "Choose a slot with the veterinarian responsible "
                    "for this follow-up.",
                )

            existing_booking = db.scalar(
                select(Appointment.appointment_id)
                .where(
                    Appointment.followup_care_id == followup.followup_care_id,
                    Appointment.status.notin_(["cancelled", "rejected"]),
                )
                .limit(1)
            )

            if existing_booking is not None:
                raise HTTPException(
                    409,
                    "This follow-up already has a booked appointment. "
                    "Open that appointment to manage it.",
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

        reject_absent_slots(db, [slot.time_slot_id])
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

        validate_scan_booking(
            db,
            current_user,
            pet,
            data.ai_analysis_id,
        )

        validate_review_booking(
            db,
            current_user,
            pet,
            clinic,
            data.ai_assessment_review_id,
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
            followup_care_id=data.followup_care_id,
            ai_assessment_review_id=data.ai_assessment_review_id,
            ai_analysis_id=data.ai_analysis_id,
            medical_history_shared_at=(
                datetime.now(timezone.utc).replace(tzinfo=None)
                if data.share_medical_history
                else None
            ),
            booking_request_id=(
                str(data.booking_request_id)
                if data.booking_request_id is not None
                else None
            ),
            booking_deposit_amount=clinic.booking_deposit_amount,
        )

        slot.status = "booked"
        db.add(appointment)
        db.flush()

        prepare_deposit_payment(
            db,
            current_user,
            schedule,
            slot,
            appointment,
        )

        from app.services.staff_notification_service import notify_booking_confirmed
        notify_booking_confirmed(db, appointment)
        db.commit()
        db.refresh(appointment)

        return appointment

    except Exception:
        db.rollback()
        raise

def list_my_appointments(
    db: Session,
    current_user: User,
    appointment_date: date | None,
    offset: int,
    limit: int,
):
    owner = get_owner_profile(db, current_user)

    # A pending task belonging to this appointment's completed consultation.
    pending_followup = (
        select(FollowupCare.followup_care_id)
        .join(
            Consultation,
            Consultation.consultation_id
            == FollowupCare.consultation_id,
        )
        .where(
            Consultation.appointment_id
            == Appointment.appointment_id,
            Consultation.pet_id == Appointment.pet_id,
            Consultation.status == "completed",
            FollowupCare.pet_id == Appointment.pet_id,
            FollowupCare.status == "pending",
        )
        .correlate(Appointment)
        .exists()
    )

    statement = (
        select(
            Appointment.appointment_id,
            Schedule.schedule_date.label("appointment_date"),
            TimeSlot.start_time,
            TimeSlot.end_time,
            Pet.pet_id,
            Pet.pet_name,
            Veterinarian.veterinarian_id,
            User.full_name.label("veterinarian_name"),
            Clinic.clinic_id,
            Clinic.clinic_name,
            Clinic.address.label("clinic_address"),
            Appointment.appointment_type,
            Appointment.status,
            Appointment.booking_deposit_amount,
            Appointment.payment_expires_at,
            pending_followup.label("has_pending_followup"),
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
        .join(User, User.user_id == Veterinarian.user_id)
        .join(Clinic, Clinic.clinic_id == Veterinarian.clinic_id)
        .join(Pet, Pet.pet_id == Appointment.pet_id)
        .where(
            Appointment.pet_owner_id == owner.pet_owner_id,
            Pet.pet_owner_id == owner.pet_owner_id,
        )
    )

    if appointment_date is not None:
        statement = statement.where(
            Schedule.schedule_date == appointment_date
        )

    statement = (
        statement
        .order_by(
            Schedule.schedule_date.desc(),
            TimeSlot.start_time.desc(),
            Appointment.appointment_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    records = db.execute(statement).mappings().all()

    rearrangement_ids = get_rearrangement_ids(
        db,
        [record["appointment_id"] for record in records],
    )

    return [
        {
            **dict(record),
            "needs_rearrangement": (
                record["appointment_id"] in rearrangement_ids
            ),
        }
        for record in records
    ]

def _lock_owned_appointment(
    db: Session,
    current_user: User,
    appointment_id: int,
):
    owner = get_owner_profile(db, current_user)

    location = db.execute(
        select(
            Appointment.time_slot_id,
            TimeSlot.schedule_id,
            Schedule.veterinarian_id,
            Veterinarian.clinic_id,
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
            Appointment.pet_owner_id == owner.pet_owner_id,
        )
    ).first()

    if location is None:
        raise HTTPException(
            404, "Appointment not found in your account."
        )

    # Preserve the booking lock order.
    clinic = db.scalar(
        select(Clinic)
        .where(Clinic.clinic_id == location.clinic_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    veterinarian = db.scalar(
        select(Veterinarian)
        .where(
            Veterinarian.veterinarian_id
            == location.veterinarian_id,
            Veterinarian.clinic_id == location.clinic_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    schedule = db.scalar(
        select(Schedule)
        .where(
            Schedule.schedule_id == location.schedule_id,
            Schedule.veterinarian_id == location.veterinarian_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    slot = db.scalar(
        select(TimeSlot)
        .where(
            TimeSlot.time_slot_id == location.time_slot_id,
            TimeSlot.schedule_id == location.schedule_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if any(
        record is None
        for record in (clinic, veterinarian, schedule, slot)
    ):
        raise HTTPException(
            409, "Appointment details changed. Refresh and try again."
        )

    appointment = db.scalar(
        select(Appointment)
        .where(
            Appointment.appointment_id == appointment_id,
            Appointment.pet_owner_id == owner.pet_owner_id,
            Appointment.time_slot_id == location.time_slot_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if appointment is None:
        raise HTTPException(
            409, "Appointment changed. Refresh and try again."
        )

    return appointment, schedule, slot, veterinarian, clinic


def cancel_my_appointment(
    db: Session,
    current_user: User,
    appointment_id: int,
):
    try:
        appointment, schedule, slot, _, _ = (
            _lock_owned_appointment(
                db, current_user, appointment_id
            )
        )

        if appointment.status == "cancelled":
            db.commit()
            return {"message": "Appointment is already cancelled."}

        if appointment.status not in ("pending", "confirmed"):
            raise HTTPException(
                409,
                "Only pending or confirmed appointments can be cancelled.",
            )

        start = datetime.combine(
            schedule.schedule_date,
            slot.start_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        if start <= datetime.now(CLINIC_TIMEZONE):
            raise HTTPException(
                409,
                "An appointment that has started cannot be cancelled.",
            )

        queue_booking_deposit_refund(
            db,
            appointment,
            schedule,
            slot,
            actor_user_id=current_user.user_id,
        )

        appointment.status = "cancelled"
        db.flush()

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

def reschedule_my_appointment(
    db: Session,
    current_user: User,
    appointment_id: int,
    new_slot_id: int,
):
    try:
        appointment, old_schedule, old_slot, _, clinic = (
            _lock_owned_appointment(
                db, current_user, appointment_id
            )
        )

        if appointment.status not in ("pending", "confirmed"):
            raise HTTPException(
                409,
                "Only pending or confirmed appointments can be rescheduled.",
            )

        if appointment.appointment_type == "emergency":
            raise HTTPException(
                409,
                "Contact the clinic to rearrange an emergency appointment.",
            )

        now = datetime.now(CLINIC_TIMEZONE)

        old_start = datetime.combine(
            old_schedule.schedule_date,
            old_slot.start_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        if old_start <= now:
            raise HTTPException(
                409,
                "An appointment that has started cannot be rescheduled.",
            )

        if clinic.status != "active":
            raise HTTPException(
                409, "This clinic is unavailable for rescheduling."
            )

        if new_slot_id == old_slot.time_slot_id:
            raise HTTPException(
                400, "Choose a different appointment slot."
            )

        target = db.execute(
            select(
                TimeSlot.schedule_id,
                Schedule.veterinarian_id,
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
                TimeSlot.time_slot_id == new_slot_id,
                Veterinarian.clinic_id == clinic.clinic_id,
            )
        ).first()

        if target is None:
            raise HTTPException(
                404, "Choose a slot at the same clinic."
            )

        if (
            appointment.followup_care_id is not None
            and target.veterinarian_id != appointment.veterinarian_id
        ):
            raise HTTPException(
                422,
                "This follow-up must remain with its assigned veterinarian. "
                "Choose another time with the same veterinarian, "
                "or contact the clinic.",
            )

        veterinarian = db.scalar(
            select(Veterinarian)
            .join(Veterinarian.user)
            .where(
                Veterinarian.veterinarian_id
                == target.veterinarian_id,
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
                409, "The selected veterinarian is unavailable."
            )

        new_schedule = db.scalar(
            select(Schedule)
            .where(
                Schedule.schedule_id == target.schedule_id,
                Schedule.veterinarian_id
                == veterinarian.veterinarian_id,
                Schedule.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if new_schedule is None:
            raise HTTPException(
                409, "The selected schedule is unavailable."
            )

        new_slot = db.scalar(
            select(TimeSlot)
            .where(
                TimeSlot.time_slot_id == new_slot_id,
                TimeSlot.schedule_id == new_schedule.schedule_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if new_slot is None or new_slot.status != "available":
            raise HTTPException(
                409, "The new slot is no longer available."
            )

        if (
            new_slot.end_time <= new_slot.start_time
            or new_slot.start_time < new_schedule.start_time
            or new_slot.end_time > new_schedule.end_time
        ):
            raise HTTPException(
                409, "The new slot has invalid working hours."
            )

        new_start = datetime.combine(
            new_schedule.schedule_date,
            new_slot.start_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        if new_start <= datetime.now(CLINIC_TIMEZONE):
            raise HTTPException(
                400, "Choose a future appointment slot."
            )

        reject_absent_slots(db, [new_slot.time_slot_id])
        reject_occupied_slots(db, [new_slot.time_slot_id])

        pet = db.scalar(
            select(Pet)
            .where(
                Pet.pet_id == appointment.pet_id,
                Pet.pet_owner_id == appointment.pet_owner_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if pet is None:
            raise HTTPException(
                409, "This pet no longer belongs to your account."
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
                "Your pet already has an overlapping appointment.",
            )

        appointment.time_slot_id = new_slot.time_slot_id
        appointment.veterinarian_id = new_schedule.veterinarian_id
        appointment.appointment_date = new_schedule.schedule_date
        new_slot.status = "booked"

        db.flush()

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
        db.refresh(appointment)

        return appointment

    except Exception:
        db.rollback()
        raise
