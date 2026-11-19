from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import and_, or_, select

from app.models import (
    Appointment,
    Clinic,
    Pet,
    Schedule,
    TimeSlot,
    User,
    Veterinarian,
)
from app.services.pet_service import get_owner_profile, get_pet
from app.services.vet_absence_service import get_rearrangement_ids
from app.services.chatbot_language_service import (
    render_upcoming_appointments,
)


MALAYSIA_TIME = timezone(timedelta(hours=8))


STATUS_TEXT = {
    "pending": "Pending clinic confirmation",
    "confirmed": "Confirmed",
    "pending_payment": (
        "Awaiting payment — this booking is not confirmed"
    ),
}


def upcoming_appointment_reply(
    db,
    current_user,
    pet_id,
    language="en",
):
    if current_user.role != "pet_owner":
        raise HTTPException(
            403,
            "A pet owner account is required.",
        )

    owner = get_owner_profile(db, current_user)

    if pet_id is None:
        return render_upcoming_appointments(
            None,
            [],
            language=language,
        )

    pet = get_pet(db, current_user, pet_id)

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(MALAYSIA_TIME)
    today = now_local.date()
    current_time = now_local.time().replace(tzinfo=None)

    records = db.execute(
        select(
            Appointment.appointment_id,
            Appointment.status,
            Appointment.appointment_type,
            Schedule.schedule_date,
            TimeSlot.start_time,
            TimeSlot.end_time,
            User.full_name.label("vet_name"),
            Clinic.clinic_name,
            Clinic.address,
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
        .join(
            User,
            User.user_id == Veterinarian.user_id,
        )
        .join(
            Clinic,
            Clinic.clinic_id == Veterinarian.clinic_id,
        )
        .join(
            Pet,
            Pet.pet_id == Appointment.pet_id,
        )
        .where(
            Appointment.pet_owner_id == owner.pet_owner_id,
            Pet.pet_owner_id == owner.pet_owner_id,
            Appointment.pet_id == pet.pet_id,
            Appointment.status.in_([
                "pending",
                "confirmed",
                "pending_payment",
            ]),
            or_(
                Schedule.schedule_date > today,
                and_(
                    Schedule.schedule_date == today,
                    TimeSlot.start_time >= current_time,
                ),
            ),
            # Do not present expired unpaid attempts as upcoming.
            or_(
                Appointment.status != "pending_payment",
                Appointment.payment_expires_at
                > now_utc.replace(tzinfo=None),
            ),
        )
        .order_by(
            Schedule.schedule_date,
            TimeSlot.start_time,
            Appointment.appointment_id,
        )
        .limit(3)
    ).mappings().all()

    if not records:
        return render_upcoming_appointments(
            pet.pet_name,
            [],
            language=language,
        )

    rearrangement_ids = get_rearrangement_ids(
        db,
        [record["appointment_id"] for record in records],
    )

    return render_upcoming_appointments(
        pet.pet_name,
        records,
        rearrangement_ids,
        language=language,
    )