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
    allocation=None,
):
    """
    Caller must lock the relevant records and commit the
    refund key and request timestamp before calling Stripe.
    """
    intent_id = payment.gateway_reference

    payment_cents = int(payment.amount * 100)
    refund_cents = refund.refund_amount * 100

    if (
        payment.payment_method != "online_banking"
        or payment.payment_purpose != "booking_deposit"
        or payment.order_id is not None
        or payment.consultation_bill_id is not None
        or payment.appointment_id != appointment.appointment_id
        or checkout.appointment_id != appointment.appointment_id
        or checkout.payment_id != payment.payment_id
        or checkout.amount_cents != payment_cents
        or checkout.currency != "myr"
        or payment.amount != appointment.booking_deposit_amount
        or payment_cents <= 0
        or refund_cents <= 0
        or refund_cents != refund_cents.to_integral_value()
        or refund.refund_amount > payment.amount
        or not isinstance(intent_id, str)
        or not intent_id.startswith("pi_")
        or len(intent_id) > 100
    ):
        raise HTTPException(
            409,
            "The refund does not match the original booking deposit.",
        )

    amount_cents = int(refund_cents)

    if refund.refund_purpose == "booking_cancellation":
        if (
            allocation is not None
            or refund.refund_amount != payment.amount
        ):
            raise HTTPException(
                409,
                "Cancellation refunds must match the full deposit.",
            )

        # Preserve the original metadata for safe retries of
        # cancellation refunds that were already submitted.
        refund_metadata = {
            "purpose": "booking_deposit_refund",
            "refund_id": str(refund.refund_id),
            "appointment_id": str(appointment.appointment_id),
            "payment_id": str(payment.payment_id),
        }

    elif refund.refund_purpose == "booking_excess":
        if (
            allocation is None
            or allocation.payment_id != payment.payment_id
            or allocation.excess_refund_id != refund.refund_id
            or allocation.deposit_amount != payment.amount
            or allocation.applied_amount < 0
            or allocation.excess_refund_amount <= 0
            or allocation.excess_refund_amount
            != refund.refund_amount
            or allocation.applied_amount
            + allocation.excess_refund_amount
            != payment.amount
        ):
            raise HTTPException(
                409,
                "The excess refund does not match its bill allocation.",
            )

        refund_metadata = {
            "purpose": "booking_excess_refund",
            "refund_id": str(refund.refund_id),
            "appointment_id": str(appointment.appointment_id),
            "payment_id": str(payment.payment_id),
            "consultation_bill_id": str(
                allocation.consultation_bill_id
            ),
        }

    else:
        raise HTTPException(
            409,
            "Unsupported booking refund purpose.",
        )

    original_metadata = expected_metadata(
        checkout,
        appointment,
    )

    client = get_stripe_client()

    try:
        intent = client.v1.payment_intents.retrieve(
            intent_id
        ).to_dict()

        metadata = intent.get("metadata") or {}

        if (
            intent.get("id") != intent_id
            or intent.get("livemode") is not False
            or intent.get("status") != "succeeded"
            or intent.get("currency") != "myr"
            or intent.get("amount") != payment_cents
            or intent.get("amount_received") != payment_cents
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