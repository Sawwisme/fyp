from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import HTTPException

from app.schemas.owner_appointments import (
    OwnerBookingCheckoutResponse,
)
from app.services.booking_payment_processor import (
    sync_booking_checkout,
    vet_is_available,
)
from app.services.booking_payment_state import (
    lock_booking_payment_context,
)
from app.services.booking_stripe_gateway import (
    validate_booking_session,
)
from app.services.pet_service import get_owner_profile
from app.services.stripe_session_service import resolve_remote_session


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_saved_attempt(context):
    appointment = context[4]
    payments = context[5]
    checkouts = context[6]

    if (
        appointment.booking_deposit_amount <= 0
        or not appointment.booking_request_id
    ):
        raise HTTPException(
            409,
            "This appointment does not require an online deposit.",
        )

    if len(payments) != 1 or len(checkouts) != 1:
        raise HTTPException(
            409,
            "The booking payment records need reconciliation.",
        )

    payment = payments[0]
    checkout = checkouts[0]

    if (
        checkout.payment_id != payment.payment_id
        or checkout.appointment_id != appointment.appointment_id
        or payment.appointment_id != appointment.appointment_id
        or payment.payment_purpose != "booking_deposit"
        or payment.payment_method not in {"online_banking", "card"}
        or payment.order_id is not None
        or payment.consultation_bill_id is not None
        or payment.amount != appointment.booking_deposit_amount
        or checkout.amount_cents != int(payment.amount * 100)
    ):
        raise HTTPException(
            409,
            "The booking deposit details need reconciliation.",
        )

    return payment, checkout


def response_for(appointment, payment, checkout, url=None):
    return OwnerBookingCheckoutResponse(
        appointment_id=appointment.appointment_id,
        appointment_status=appointment.status,
        deposit_amount=appointment.booking_deposit_amount,
        payment_status=payment.payment_status,
        checkout_status=checkout.session_status,
        checkout_url=url,
        payment_expires_at=appointment.payment_expires_at,
    )


def ensure_can_open(db, context):
    clinic, veterinarian, schedule, slot, appointment, _, _ = context

    if (
        clinic.status != "active"
        or veterinarian.approval_status != "approved"
        or veterinarian.user.status != "active"
        or veterinarian.user.role != "veterinarian"
        or schedule.status != "active"
        or slot.status != "booked"
        or not vet_is_available(
            db,
            veterinarian,
            schedule,
            slot,
        )
    ):
        raise HTTPException(
            409,
            "This booking is unavailable for payment. "
            "Contact the clinic before paying.",
        )

    if (
        appointment.payment_expires_at is None
        or appointment.payment_expires_at <= utc_now()
    ):
        raise HTTPException(
            409,
            "The payment window has ended. "
            "Refresh the appointment to check its status.",
        )


def validate_checkout_url(value):
    try:
        if not isinstance(value, str):
            raise ValueError

        parsed = urlsplit(value)

        if (
            parsed.scheme != "https"
            or parsed.hostname != "checkout.stripe.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise ValueError

    except ValueError:
        raise HTTPException(
            502,
            "Stripe returned an invalid checkout link.",
        ) from None

    return value


def open_booking_checkout(db, current_user, appointment_id):
    try:
        owner = get_owner_profile(db, current_user)
        owner_id = owner.pet_owner_id

        # Check ownership before allowing payment synchronization.
        context = lock_booking_payment_context(
            db,
            appointment_id,
            owner_id=owner_id,
        )

        appointment = context[4]
        payment, checkout = get_saved_attempt(context)

        if (
            appointment.status != "pending_payment"
            or payment.payment_status != "pending"
            or checkout.session_status == "review_required"
        ):
            result = response_for(
                appointment,
                payment,
                checkout,
            )
            db.commit()
            return result

        checkout_id = checkout.booking_checkout_id

        # Release these locks before the processor acquires
        # its complete booking/payment context.
        db.commit()

        # Uses the saved payload and idempotency key.
        # This may confirm payment, expire checkout, or keep
        # an unresolved bank payment reserved.
        sync_booking_checkout(db, checkout_id)

        context = lock_booking_payment_context(
            db,
            appointment_id,
            owner_id=owner_id,
        )

        appointment = context[4]
        payment, checkout = get_saved_attempt(context)

        if (
            appointment.status != "pending_payment"
            or payment.payment_status != "pending"
            or checkout.session_status != "open"
        ):
            result = response_for(
                appointment,
                payment,
                checkout,
            )
            db.commit()
            return result

        ensure_can_open(db, context)

        # Retrieve the canonical state once more before exposing
        # a checkout link to the owner.
        remote = resolve_remote_session(checkout)

        validate_booking_session(
            remote,
            checkout,
            payment,
            appointment,
        )

        if (
            remote.get("status") != "open"
            or remote.get("payment_status") != "unpaid"
        ):
            checkout.session_status = "processing"
            checkout.checkout_url = None

            result = response_for(
                appointment,
                payment,
                checkout,
            )

            db.commit()
            return result

        expiry = remote.get("expires_at")

        if not isinstance(expiry, int) or isinstance(expiry, bool):
            raise HTTPException(
                502,
                "Stripe returned an invalid checkout expiry.",
            )

        expiry_time = datetime.fromtimestamp(
            expiry,
            tz=timezone.utc,
        ).replace(tzinfo=None)

        if expiry_time <= utc_now():
            raise HTTPException(
                409,
                "The checkout has expired. Refresh the appointment.",
            )

        # The local payment deadline may have elapsed
        # while waiting for Stripe's response.
        ensure_can_open(db, context)

        url = validate_checkout_url(remote.get("url"))

        checkout.checkout_url = url
        checkout.expires_at = expiry_time

        result = response_for(
            appointment,
            payment,
            checkout,
            url=url,
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise