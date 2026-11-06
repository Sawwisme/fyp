from fastapi import HTTPException


def verified_payment_method(intent, payment):
    """
    Read the actual method from a verified successful charge.

    Retrieve the PaymentIntent with latest_charge expanded.
    Keep the existing metadata verification in each payment flow.
    """
    intent_id = intent.get("id")
    charge = intent.get("latest_charge")

    if not isinstance(charge, dict):
        raise HTTPException(
            409,
            "The payment charge details need verification.",
        )

    expected_amount = int(payment.amount * 100)

    if (
        not isinstance(intent_id, str)
        or not intent_id.startswith("pi_")
        or intent.get("livemode") is not False
        or intent.get("status") != "succeeded"
        or intent.get("currency") != "myr"
        or intent.get("amount") != expected_amount
        or intent.get("amount_received") != expected_amount
        or charge.get("payment_intent") != intent_id
        or charge.get("livemode") is not False
        or charge.get("status") != "succeeded"
        or charge.get("paid") is not True
        or charge.get("captured") is not True
        or charge.get("currency") != "myr"
        or charge.get("amount") != expected_amount
        or charge.get("amount_captured") != expected_amount
    ):
        raise HTTPException(
            409,
            "The payment charge does not match this payment.",
        )

    details = charge.get("payment_method_details") or {}
    method = details.get("type")

    if method == "card":
        return "card"

    if method == "fpx":
        return "online_banking"

    raise HTTPException(
        409,
        "This payment method is not supported.",
    )