from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.clinic_time import CLINIC_TIMEZONE
from app.models import Payment, PetOwner, Refund, Transaction


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def queue_booking_deposit_refund(
    db,
    appointment,
    schedule,
    slot,
    actor_user_id,
):
    """
    Caller must already hold the clinic and appointment locks.

    This only queues the refund. It does not contact Stripe
    or mark the payment as refunded.
    """
    payments = db.scalars(
        select(Payment)
        .where(
            Payment.appointment_id == appointment.appointment_id,
            Payment.payment_purpose == "booking_deposit",
        )
        .order_by(Payment.payment_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    if appointment.booking_deposit_amount == 0 and not payments:
        return None

    if len(payments) != 1:
        raise HTTPException(
            409,
            "The booking deposit records need reconciliation "
            "before cancellation.",
        )

    payment = payments[0]

    if (
        not appointment.booking_request_id
        or appointment.booking_deposit_amount <= 0
        or payment.amount != appointment.booking_deposit_amount
        or payment.order_id is not None
        or payment.consultation_bill_id is not None
        or payment.payment_method != "online_banking"
        or payment.payment_status not in {"paid", "refunded"}
        or payment.payment_date is None
        or not isinstance(payment.gateway_reference, str)
        or not payment.gateway_reference.startswith("pi_")
    ):
        raise HTTPException(
            409,
            "The booking deposit must be checked "
            "before cancellation.",
        )

    payer_user_id = db.scalar(
        select(PetOwner.user_id)
        .where(
            PetOwner.pet_owner_id == appointment.pet_owner_id,
        )
    )

    transactions = db.scalars(
        select(Transaction)
        .where(
            Transaction.payment_id == payment.payment_id,
            Transaction.transaction_type == "payment",
        )
        .order_by(Transaction.transaction_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    if len(transactions) != 1:
        raise HTTPException(
            409,
            "The original deposit transaction needs reconciliation.",
        )

    transaction = transactions[0]

    if (
        transaction.order_id is not None
        or transaction.user_id != payer_user_id
        or transaction.amount != payment.amount
        or transaction.transaction_status != "completed"
    ):
        raise HTTPException(
            409,
            "The deposit does not match its original transaction.",
        )

    refunds = db.scalars(
        select(Refund)
        .where(
            Refund.transaction_id == transaction.transaction_id,
        )
        .order_by(Refund.refund_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    if refunds:
        if len(refunds) != 1:
            raise HTTPException(
                409,
                "Multiple deposit refunds need reconciliation.",
            )

        existing = refunds[0]

        if (
            existing.refund_purpose != "booking_cancellation"
            or existing.refund_amount != payment.amount
            or existing.status not in {
                "approved",
                "processing",
                "requires_action",
                "failed",
                "succeeded",
            }
            or (
                existing.status == "succeeded"
                and payment.payment_status != "refunded"
            )
            or (
                payment.payment_status == "refunded"
                and existing.status != "succeeded"
            )
        ):
            raise HTTPException(
                409,
                "The existing deposit refund needs reconciliation.",
            )

        # Reuse the original refund, including failed or
        # uncertain attempts. Never create a replacement.
        return existing

    if payment.payment_status == "refunded":
        raise HTTPException(
            409,
            "The refunded deposit has no matching refund record.",
        )

    start = datetime.combine(
        schedule.schedule_date,
        slot.start_time,
        tzinfo=CLINIC_TIMEZONE,
    )

    if start <= datetime.now(CLINIC_TIMEZONE):
        raise HTTPException(
            409,
            "This appointment has already started. "
            "Contact the clinic to review its payment.",
        )

    now = utc_now()

    refund = Refund(
        transaction_id=transaction.transaction_id,
        requested_by=actor_user_id,
        approved_by=None,
        refund_amount=payment.amount,
        reason=(
            f"Appointment #{appointment.appointment_id} "
            "cancelled before its scheduled start."
        ),
        status="approved",
        version=1,
        review_notes=(
            "Automatically approved under the full-deposit-refund "
            "policy for cancellation before the appointment starts."
        ),
        reviewed_at=now,
        requested_at=now,
        gateway_idempotency_key=str(uuid4()),
        gateway_requested_at=None,
        refund_purpose="booking_cancellation",
    )

    db.add(refund)
    db.flush()

    return refund