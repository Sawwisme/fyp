from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from stripe import StripeError

from app.services.stripe_gateway import get_stripe_client


def resolve_stripe_refund(refund, payment, order) -> dict:
    """
    Caller must lock the relevant database rows and persist
    the idempotency key and request timestamp before calling.
    """
    intent_id = payment.gateway_reference
    cents = refund.refund_amount * Decimal("100")

    if (
        payment.payment_method not in {"online_banking", "card"}
        or not isinstance(intent_id, str)
        or not intent_id.startswith("pi_")
        or len(intent_id) > 100
        or cents <= 0
        or cents != cents.to_integral_value()
        or refund.refund_amount != payment.amount
        or refund.refund_amount != order.total_amount
    ):
        raise HTTPException(
            409,
            "The refund does not match the original online payment.",
        )

    amount_cents = int(cents)

    expected_metadata = {
        "refund_id": str(refund.refund_id),
        "order_id": str(order.order_id),
        "payment_id": str(payment.payment_id),
    }

    client = get_stripe_client()

    try:
        intent = client.v1.payment_intents.retrieve(
            intent_id
        ).to_dict()

        intent_metadata = intent.get("metadata") or {}

        if (
            intent.get("id") != intent_id
            or intent.get("livemode") is not False
            or intent.get("status") != "succeeded"
            or intent.get("currency") != "myr"
            or intent.get("amount") != amount_cents
            or intent.get("amount_received") != amount_cents
            or intent_metadata.get("order_id")
            != str(order.order_id)
            or intent_metadata.get("payment_id")
            != str(payment.payment_id)
        ):
            raise HTTPException(
                409,
                "Stripe payment verification failed. "
                "The payment needs reconciliation.",
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
                    "This refund request requires reconciliation. "
                    "Do not create a replacement refund.",
                )

            created = client.v1.refunds.create(
                params={
                    "payment_intent": intent_id,
                    "amount": amount_cents,
                    "reason": "requested_by_customer",
                    "metadata": expected_metadata,
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
                "Invalid stored Stripe refund reference.",
            )

        # A retry can replay the original creation response.
        # Retrieve the refund to obtain its current status.
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
                for key, value in expected_metadata.items()
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
                "the approved request.",
            )

        return remote

    except StripeError:
        raise HTTPException(
            503,
            "Stripe refund status could not be confirmed. "
            "Reload and retry the same refund request.",
        ) from None