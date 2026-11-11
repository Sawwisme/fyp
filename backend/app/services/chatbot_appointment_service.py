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


MALAYSIA_TIME = timezone(timedelta(hours=8))


STATUS_TEXT = {
    "pending": "Pending clinic confirmation",
    "confirmed": "Confirmed",
    "pending_payment": (
        "Awaiting payment — this booking is not confirmed"
    ),
}


def upcoming_appointment_reply(db, current_user, pet_id):
    if current_user.role != "pet_owner":
        raise HTTPException(
            403,
            "A pet owner account is required.",
        )

    owner = get_owner_profile(db, current_user)

    if pet_id is None:
        return (
            "Select a pet by starting a new pet-linked chat "
            "so I can check its upcoming appointments."
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
        return (
            f"I do not see an upcoming pending, confirmed or "
            f"unexpired payment-pending appointment for {pet.pet_name}. "
            "Open Booking to check all appointments or choose a time."
        )

    rearrangement_ids = get_rearrangement_ids(
        db,
        [record["appointment_id"] for record in records],
    )

    sections = [
        f"Next upcoming bookings for {pet.pet_name} "
        "(Malaysia time):"
    ]

    for record in records:
        appointment_id = record["appointment_id"]

        status = STATUS_TEXT.get(
            record["status"],
            record["status"],
        )

        date = record["schedule_date"].strftime("%d %b %Y")
        start = record["start_time"].strftime("%H:%M")
        end = record["end_time"].strftime("%H:%M")

        section = (
            f"Appointment #{appointment_id}\n"
            f"Date: {date}, {start}–{end}\n"
            f"Clinic: {record['clinic_name']}\n"
            f"Veterinarian: {record['vet_name']}\n"
            f"Type: {record['appointment_type']}\n"
            f"Status: {status}\n"
            f"Address: {record['address'] or 'Not recorded'}"
        )

        if appointment_id in rearrangement_ids:
            section += (
                "\nAttention: this appointment needs rearrangement "
                "because of a reported veterinarian absence. "
                "Open its booking details or contact the clinic."
            )

        sections.append(section)

    sections.append(
        "Open Booking to view or manage these appointments. "
        "This chat has not created or changed a booking."
    )

    return "\n\n".join(sections)