from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.clinic_time import CLINIC_TIMEZONE
from app.models import (
    Appointment,
    BookingStripeSession,
    Clinic,
    Payment,
)
from app.schemas.clinic_booking_payment import (
    BookingPaymentSettingsResponse,
)
from app.services.booking_stripe_gateway import expected_metadata
from app.services.pet_service import get_owner_profile
from app.services.stripe_checkout_service import get_return_url
from app.services.stripe_gateway import get_stripe_client


def get_booking_quote(db, current_user, clinic_id):
    get_owner_profile(db, current_user)

    clinic = db.scalar(
        select(Clinic)
        .where(
            Clinic.clinic_id == clinic_id,
            Clinic.status == "active",
        )
        .execution_options(populate_existing=True)
    )

    if clinic is None:
        raise HTTPException(404, "Clinic unavailable.")

    return BookingPaymentSettingsResponse(
        clinic_id=clinic.clinic_id,
        deposit_amount=clinic.booking_deposit_amount,
        version=clinic.booking_payment_version,
    )


def prepare_booking_request(db, owner, clinic, data):
    request_id = (
        str(data.booking_request_id)
        if data.booking_request_id is not None
        else None
    )

    if request_id is None:
        if (
            data.expected_payment_version is not None
            or data.expected_deposit_amount is not None
        ):
            raise HTTPException(
                422,
                "A booking request ID is required.",
            )

        if clinic.booking_deposit_amount > 0:
            raise HTTPException(
                409,
                "This clinic requires a booking deposit. "
                "Refresh the booking details before continuing.",
            )

        return None

    if (
        data.expected_payment_version is None
        or data.expected_deposit_amount is None
    ):
        raise HTTPException(
            422,
            "Confirm the clinic's deposit settings before booking.",
        )

    existing = db.scalar(
        select(Appointment)
        .where(
            Appointment.booking_request_id == request_id,
        )
        .execution_options(populate_existing=True)
    )

    if existing is not None:
        if (
            existing.pet_owner_id != owner.pet_owner_id
            or existing.pet_id != data.pet_id
            or existing.time_slot_id != data.time_slot_id
            or existing.appointment_type != data.appointment_type
            or existing.followup_care_id != data.followup_care_id
            or existing.booking_deposit_amount
            != data.expected_deposit_amount
        ):
            raise HTTPException(
                409,
                "This booking request ID was already used "
                "for different booking details.",
            )

        # Return the original result after a timeout or retry.
        # Never create a second appointment or deposit.
        return existing

    if (
        clinic.booking_payment_version
        != data.expected_payment_version
        or clinic.booking_deposit_amount
        != data.expected_deposit_amount
    ):
        raise HTTPException(
            409,
            "The clinic's deposit setting changed. "
            "Refresh and confirm the amount again.",
        )

    return None


def prepare_deposit_payment(
    db,
    current_user,
    schedule,
    slot,
    appointment,
):
    amount = appointment.booking_deposit_amount

    if amount <= 0:
        return

    if not appointment.booking_request_id:
        raise HTTPException(
            422,
            "A booking request ID is required for deposit payment.",
        )

    # Validate configuration before committing a reservation.
    # This does not send a Stripe request.
    get_stripe_client()

    parsed = urlsplit(get_return_url())

    return_url = urlunsplit((
        parsed.scheme,
        parsed.netloc,
        "/owner-appointments/stripe/return",
        "",
        "",
    ))

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    appointment_start = datetime.combine(
        schedule.schedule_date,
        slot.start_time,
        tzinfo=CLINIC_TIMEZONE,
    ).astimezone(timezone.utc).replace(tzinfo=None)

    deadline = min(
        now + timedelta(minutes=15),
        appointment_start,
    )

    if deadline <= now:
        raise HTTPException(
            409,
            "This appointment slot has already started.",
        )

    appointment.status = "pending_payment"
    appointment.payment_expires_at = deadline

    payment = Payment(
        order_id=None,
        appointment_id=appointment.appointment_id,
        consultation_bill_id=None,
        payment_purpose="booking_deposit",
        payment_method="online_banking",
        payment_status="pending",
        amount=amount,
    )

    db.add(payment)
    db.flush()

    checkout = BookingStripeSession(
        appointment_id=appointment.appointment_id,
        payment_id=payment.payment_id,
        idempotency_key=str(uuid4()),
        amount_cents=int(amount * 100),
        currency="myr",
        session_status="creating",
        created_at=now,
    )

    metadata = expected_metadata(checkout, appointment)

    # Persist the exact request and key before contacting Stripe.
    # The worker can safely recover an interrupted request.
    checkout.request_payload = {
        "mode": "payment",
        "payment_method_types": ["fpx"],
        "client_reference_id": (
            f"booking:{appointment.appointment_id}"
        ),
        "customer_email": current_user.email,
        "metadata": metadata,
        "payment_intent_data": {
            "metadata": metadata,
        },
        "line_items": [
            {
                "price_data": {
                    "currency": "myr",
                    "unit_amount": checkout.amount_cents,
                    "product_data": {
                        "name": (
                            "Appointment deposit "
                            f"#{appointment.appointment_id}"
                        ),
                    },
                },
                "quantity": 1,
            },
        ],
        "success_url": return_url,
        "cancel_url": return_url,
    }

    db.add(checkout)