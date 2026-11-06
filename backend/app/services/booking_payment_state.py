from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    Appointment,
    BookingStripeSession,
    Clinic,
    Payment,
    Pet,
    Schedule,
    TimeSlot,
    Veterinarian,
)


def lock_record(db, model, **conditions):
    return db.scalar(
        select(model)
        .filter_by(**conditions)
        .execution_options(populate_existing=True)
        .with_for_update()
    )


def lock_booking_payment_context(
    db,
    appointment_id,
    owner_id=None,
):
    statement = (
        select(
            Appointment.pet_id,
            Appointment.pet_owner_id,
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
        )
    )

    if owner_id is not None:
        statement = statement.where(
            Appointment.pet_owner_id == owner_id,
        )

    location = db.execute(statement).first()

    if location is None:
        raise HTTPException(404, "Appointment not found.")

    # Match the booking services' locking order.
    # Inactive clinics must still allow payment reconciliation.
    clinic = lock_record(
        db,
        Clinic,
        clinic_id=location.clinic_id,
    )

    veterinarian = lock_record(
        db,
        Veterinarian,
        veterinarian_id=location.veterinarian_id,
        clinic_id=location.clinic_id,
    )

    schedule = lock_record(
        db,
        Schedule,
        schedule_id=location.schedule_id,
        veterinarian_id=location.veterinarian_id,
    )

    slot = lock_record(
        db,
        TimeSlot,
        time_slot_id=location.time_slot_id,
        schedule_id=location.schedule_id,
    )

    pet = lock_record(
        db,
        Pet,
        pet_id=location.pet_id,
        pet_owner_id=location.pet_owner_id,
    )

    appointment = lock_record(
        db,
        Appointment,
        appointment_id=appointment_id,
        pet_owner_id=location.pet_owner_id,
        pet_id=location.pet_id,
        time_slot_id=location.time_slot_id,
    )

    if any(
        record is None
        for record in (
            clinic,
            veterinarian,
            schedule,
            slot,
            pet,
            appointment,
        )
    ):
        raise HTTPException(
            409,
            "Booking details changed. Refresh and try again.",
        )

    if appointment.veterinarian_id != veterinarian.veterinarian_id:
        raise HTTPException(
            409,
            "The booking's veterinarian needs reconciliation.",
        )

    payments = db.scalars(
        select(Payment)
        .where(
            Payment.appointment_id == appointment_id,
            Payment.payment_purpose == "booking_deposit",
        )
        .order_by(Payment.payment_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    checkouts = db.scalars(
        select(BookingStripeSession)
        .where(
            BookingStripeSession.appointment_id == appointment_id,
        )
        .order_by(BookingStripeSession.booking_checkout_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    return (
        clinic,
        veterinarian,
        schedule,
        slot,
        appointment,
        payments,
        checkouts,
    )