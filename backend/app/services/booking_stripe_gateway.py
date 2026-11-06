from fastapi import HTTPException
from stripe import StripeError

from app.services.stripe_gateway import get_stripe_client


def expected_metadata(checkout, appointment):
    return {
        "purpose": "booking_deposit",
        "appointment_id": str(appointment.appointment_id),
        "payment_id": str(checkout.payment_id),
        "booking_request_id": appointment.booking_request_id,
    }


def validate_booking_session(
    remote,
    checkout,
    payment,
    appointment,
):
    metadata = remote.get("metadata") or {}
    expected = expected_metadata(checkout, appointment)

    if (
        not appointment.booking_request_id
        or not checkout.stripe_session_id
        or not checkout.stripe_session_id.startswith("cs_test_")
        or remote.get("id") != checkout.stripe_session_id
        or remote.get("livemode") is not False
        or remote.get("mode") != "payment"
        or remote.get("client_reference_id")
        != f"booking:{appointment.appointment_id}"
        or remote.get("currency") != "myr"
        or checkout.currency != "myr"
        or remote.get("amount_total") != checkout.amount_cents
        or checkout.amount_cents != int(payment.amount * 100)
        or checkout.appointment_id != appointment.appointment_id
        or payment.payment_id != checkout.payment_id
        or payment.appointment_id != appointment.appointment_id
        or payment.order_id is not None
        or payment.consultation_bill_id is not None
        or payment.payment_purpose != "booking_deposit"
        or payment.payment_method != "online_banking"
        or payment.amount != appointment.booking_deposit_amount
        or payment.amount <= 0
        or any(
            metadata.get(key) != value
            for key, value in expected.items()
        )
    ):
        raise HTTPException(
            409,
            "Stripe checkout does not match this booking deposit.",
        )


def verify_booking_payment_intent(
    remote,
    checkout,
    payment,
    appointment,
):
    validate_booking_session(
        remote,
        checkout,
        payment,
        appointment,
    )

    if (
        remote.get("status") != "complete"
        or remote.get("payment_status") != "paid"
    ):
        raise HTTPException(
            409,
            "The booking deposit is not confirmed yet.",
        )

    intent_id = remote.get("payment_intent")

    if (
        not isinstance(intent_id, str)
        or not intent_id.startswith("pi_")
        or len(intent_id) > 100
    ):
        raise HTTPException(
            409,
            "Missing Stripe payment reference.",
        )

    try:
        intent = get_stripe_client().v1.payment_intents.retrieve(
            intent_id
        ).to_dict()

    except StripeError:
        raise HTTPException(
            503,
            "Cannot confirm the booking deposit yet. "
            "Refresh again shortly.",
        ) from None

    metadata = intent.get("metadata") or {}
    expected = expected_metadata(checkout, appointment)

    if (
        intent.get("id") != intent_id
        or intent.get("livemode") is not False
        or intent.get("status") != "succeeded"
        or intent.get("currency") != "myr"
        or intent.get("amount") != checkout.amount_cents
        or intent.get("amount_received") != checkout.amount_cents
        or payment.gateway_reference not in (None, intent_id)
        or any(
            metadata.get(key) != value
            for key, value in expected.items()
        )
    ):
        raise HTTPException(
            409,
            "Stripe payment verification failed for this booking.",
        )

    return intent_id