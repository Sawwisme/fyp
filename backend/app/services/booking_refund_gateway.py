from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from stripe import StripeError

from app.services.booking_stripe_gateway import expected_metadata
from app.services.stripe_gateway import get_stripe_client


def resolve_booking_refund(
    refund,
    payment,
    appointment,
    checkout,
):
    """
    Caller must lock the booking/payment/refund records and
    commit the refund idempotency key and request timestamp
    before calling this function.
    """
    intent_id = payment.gateway_reference
    amount_cents = int(payment.amount * 100)

    if (
        payment.payment_method != "online_banking"
        or payment.payment_purpose != "booking_deposit"
        or payment.order_id is not None
        or payment.consultation_bill_id is not None
        or payment.appointment_id != appointment.appointment_id
        or checkout.appointment_id != appointment.appointment_id
        or checkout.payment_id != payment.payment_id
        or checkout.amount_cents != amount_cents
        or checkout.currency != "myr"
        or refund.refund_amount != payment.amount
        or refund.refund_amount != appointment.booking_deposit_amount
        or amount_cents <= 0
        or not isinstance(intent_id, str)
        or not intent_id.startswith("pi_")
        or len(intent_id) > 100
    ):
        raise HTTPException(
            409,
            "The refund does not match the original booking deposit.",
        )

    original_metadata = expected_metadata(
        checkout,
        appointment,
    )

    refund_metadata = {
        "purpose": "booking_deposit_refund",
        "refund_id": str(refund.refund_id),
        "appointment_id": str(appointment.appointment_id),
        "payment_id": str(payment.payment_id),
    }

    client = get_stripe_client()

    try:
        # Verify the original payment before requesting money back.
        intent = client.v1.payment_intents.retrieve(
            intent_id
        ).to_dict()

        metadata = intent.get("metadata") or {}

        if (
            intent.get("id") != intent_id
            or intent.get("livemode") is not False
            or intent.get("status") != "succeeded"
            or intent.get("currency") != "myr"
            or intent.get("amount") != amount_cents
            or intent.get("amount_received") != amount_cents
            or any(
                metadata.get(key) != value
                for key, value in original_metadata.items()
            )
        ):
            raise HTTPException(
                409,
                "The original Stripe deposit needs reconciliation.",
            )

        remote_id = refund.gateway_refund_id

        if remote_id is None:
            requested_at = refund.gateway_requested_at

            if requested_at is not None and requested_at.tzinfo is None:
                requested_at = requested_at.replace(
                    tzinfo=timezone.utc
                )

            now = datetime.now(timezone.utc)

            if (
                not refund.gateway_idempotency_key
                or requested_at is None
                or requested_at > now
                or now - requested_at >= timedelta(hours=23)
            ):
                raise HTTPException(
                    409,
                    "This refund needs reconciliation. "
                    "Do not create a replacement refund.",
                )

            created = client.v1.refunds.create(
                params={
                    "payment_intent": intent_id,
                    "amount": amount_cents,
                    "metadata": refund_metadata,
                },
                options={
                    "idempotency_key":
                        refund.gateway_idempotency_key,
                },
            ).to_dict()

            remote_id = created.get("id")

            if (
                not isinstance(remote_id, str)
                or not remote_id.startswith("re_")
                or len(remote_id) > 100
            ):
                raise HTTPException(
                    502,
                    "Unexpected Stripe refund response.",
                )

            refund.gateway_refund_id = remote_id

        elif (
            not isinstance(remote_id, str)
            or not remote_id.startswith("re_")
            or len(remote_id) > 100
        ):
            raise HTTPException(
                409,
                "Invalid stored booking refund reference.",
            )

        # An idempotent retry may replay the original creation
        # response. Retrieve the refund's current state.
        remote = client.v1.refunds.retrieve(
            remote_id
        ).to_dict()

        metadata = remote.get("metadata") or {}

        if (
            remote.get("id") != remote_id
            or remote.get("object") != "refund"
            or remote.get("payment_intent") != intent_id
            or remote.get("currency") != "myr"
            or remote.get("amount") != amount_cents
            or any(
                metadata.get(key) != value
                for key, value in refund_metadata.items()
            )
            or remote.get("status") not in {
                "pending",
                "requires_action",
                "succeeded",
                "failed",
                "canceled",
            }
        ):
            raise HTTPException(
                409,
                "Stripe refund verification did not match "
                "the booking refund request.",
            )

        return remote

    except StripeError:
        raise HTTPException(
            503,
            "Cannot confirm the booking refund status. "
            "Retry the existing refund request.",
        ) from None
