from fastapi import HTTPException
from stripe import StripeError

from app.services.stripe_gateway import get_stripe_client
from app.services.stripe_payment_method_service import verified_payment_method


def expected_metadata(checkout, bill, appointment):
    return {
        "purpose": "consultation_balance",
        "bill_id": str(bill.consultation_bill_id),
        "payment_id": str(checkout.payment_id),
        "appointment_id": str(appointment.appointment_id),
    }


def validate_bill_session(
    remote,
    checkout,
    bill,
    payment,
    appointment,
):
    metadata = remote.get("metadata") or {}
    expected = expected_metadata(checkout, bill, appointment)

    if (
        remote.get("id") != checkout.stripe_session_id
        or remote.get("livemode") is not False
        or remote.get("mode") != "payment"
        or remote.get("client_reference_id")
        != f"bill:{bill.consultation_bill_id}"
        or remote.get("currency") != "myr"
        or remote.get("currency") != checkout.currency
        or remote.get("amount_total") != checkout.amount_cents
        or checkout.amount_cents != int(payment.amount * 100)
        or checkout.consultation_bill_id
        != bill.consultation_bill_id
        or payment.consultation_bill_id
        != bill.consultation_bill_id
        or payment.payment_id != checkout.payment_id
        or payment.appointment_id != appointment.appointment_id
        or payment.order_id is not None
        or payment.payment_purpose != "consultation_balance"
        or payment.payment_method not in {"online_banking", "card"}
        or payment.amount != bill.balance_amount
        or payment.amount <= 0
        or any(
            metadata.get(key) != value
            for key, value in expected.items()
        )
    ):
        raise HTTPException(
            409,
            "Stripe checkout does not match this consultation bill.",
        )


def verify_bill_payment_intent(
    remote,
    checkout,
    bill,
    payment,
    appointment,
):
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
            intent_id,
            params={"expand": ["latest_charge"]},
        ).to_dict()

    except StripeError:
        raise HTTPException(
            503,
            "Cannot confirm the bill payment yet. "
            "Refresh again shortly.",
        ) from None

    metadata = intent.get("metadata") or {}
    expected = expected_metadata(checkout, bill, appointment)

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
            "Stripe payment verification failed for this bill.",
        )

    payment.payment_method = verified_payment_method(intent, payment)

    return intent_id