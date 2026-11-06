from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    Notification,
    Payment,
    PetOwner,
    Refund,
    Transaction,
)
from app.services.booking_checkout_service import get_saved_attempt
from app.services.booking_payment_state import (
    lock_booking_payment_context,
)
from app.services.booking_refund_gateway import (
    resolve_booking_refund,
)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_result(appointment, payment, refund):
    return {
        "appointment_id": appointment.appointment_id,
        "payment_id": payment.payment_id,
        "refund_id": refund.refund_id,
        "refund_status": refund.status,
        "refund_amount": str(refund.refund_amount),
        "payment_status": payment.payment_status,
    }


def lock_refund_context(db, refund_id):
    location = db.execute(
        select(
            Payment.appointment_id,
            Transaction.transaction_id,
        )
        .join(
            Transaction,
            Transaction.payment_id == Payment.payment_id,
        )
        .join(
            Refund,
            Refund.transaction_id == Transaction.transaction_id,
        )
        .where(
            Refund.refund_id == refund_id,
            Payment.payment_purpose == "booking_deposit",
            Payment.order_id.is_(None),
            Transaction.order_id.is_(None),
            Transaction.transaction_type == "payment",
        )
    ).first()

    if location is None or location.appointment_id is None:
        raise HTTPException(404, "Booking refund not found.")

    context = lock_booking_payment_context(
        db,
        location.appointment_id,
    )

    appointment = context[4]
    payment, checkout = get_saved_attempt(context)

    transaction = db.scalar(
        select(Transaction)
        .where(
            Transaction.transaction_id == location.transaction_id,
            Transaction.payment_id == payment.payment_id,
            Transaction.transaction_type == "payment",
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if transaction is None:
        raise HTTPException(
            409,
            "The original deposit transaction is unavailable.",
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

    if len(refunds) != 1 or refunds[0].refund_id != refund_id:
        raise HTTPException(
            409,
            "The booking refund records need reconciliation.",
        )

    refund = refunds[0]

    payer_user_id = db.scalar(
        select(PetOwner.user_id)
        .where(
            PetOwner.pet_owner_id == appointment.pet_owner_id,
        )
    )

    if (
        appointment.status != "cancelled"
        or transaction.order_id is not None
        or transaction.user_id != payer_user_id
        or transaction.transaction_status != "completed"
        or transaction.amount != payment.amount
        or refund.refund_amount != payment.amount
        or payment.payment_date is None
    ):
        raise HTTPException(
            409,
            "The refund does not match a cancelled, paid booking.",
        )

    return appointment, payment, checkout, transaction, refund


def ensure_refund_transaction(
    db,
    payment,
    transaction,
    refund,
    create=False,
):
    records = db.scalars(
        select(Transaction)
        .where(
            Transaction.payment_id == payment.payment_id,
            Transaction.transaction_type == "refund",
        )
        .order_by(Transaction.transaction_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    if len(records) > 1:
        raise HTTPException(
            409,
            "Multiple refund transactions need reconciliation.",
        )

    if records:
        existing = records[0]

        if (
            existing.order_id is not None
            or existing.user_id != transaction.user_id
            or existing.amount != refund.refund_amount
            or existing.transaction_status != "completed"
        ):
            raise HTTPException(
                409,
                "The refund transaction needs reconciliation.",
            )

        return

    if not create:
        raise HTTPException(
            409,
            "The successful refund has no matching transaction.",
        )

    db.add(
        Transaction(
            user_id=transaction.user_id,
            order_id=None,
            payment_id=payment.payment_id,
            transaction_type="refund",
            amount=refund.refund_amount,
            transaction_status="completed",
            transaction_date=utc_now(),
        )
    )


def terminal_result(db, appointment, payment, transaction, refund):
    if refund.status == "succeeded":
        if payment.payment_status != "refunded":
            raise HTTPException(
                409,
                "The successful refund payment needs reconciliation.",
            )

        ensure_refund_transaction(
            db,
            payment,
            transaction,
            refund,
        )

        return build_result(appointment, payment, refund)

    if payment.payment_status != "paid":
        raise HTTPException(
            409,
            "This deposit is not available for refund processing.",
        )

    if refund.status == "failed":
        # A failed refund requires review. Do not silently
        # create a replacement or change its idempotency key.
        return build_result(appointment, payment, refund)

    return None


def notify_refund_success(db, appointment, transaction, refund):
    if transaction.user_id is None:
        return

    event_key = f"booking-refund:{refund.refund_id}:succeeded"

    existing = db.scalar(
        select(Notification.notification_id)
        .where(
            Notification.user_id == transaction.user_id,
            Notification.event_key == event_key,
        )
        .limit(1)
    )

    if existing is not None:
        return

    db.add(
        Notification(
            user_id=transaction.user_id,
            event_key=event_key,
            notification_type="booking_deposit_refunded",
            title="Appointment deposit refunded",
            message=(
                f"Your deposit refund of "
                f"RM {refund.refund_amount:.2f} for appointment "
                f"#{appointment.appointment_id} was confirmed."
            ),
            resource_type="appointment",
            resource_id=appointment.appointment_id,
        )
    )


def process_booking_refund(db, refund_id):
    try:
        (
            appointment,
            payment,
            checkout,
            transaction,
            refund,
        ) = lock_refund_context(db, refund_id)

        result = terminal_result(
            db,
            appointment,
            payment,
            transaction,
            refund,
        )

        if result is not None:
            db.commit()
            return result

        if refund.status == "approved":
            if (
                refund.gateway_requested_at is not None
                or refund.gateway_refund_id is not None
            ):
                raise HTTPException(
                    409,
                    "The approved refund has conflicting gateway details.",
                )

            refund.gateway_idempotency_key = (
                refund.gateway_idempotency_key
                or str(uuid4())
            )
            refund.gateway_requested_at = utc_now()
            refund.status = "processing"
            refund.version += 1

        elif refund.status not in {"processing", "requires_action"}:
            raise HTTPException(
                409,
                "This booking refund is not approved for processing.",
            )

        if (
            not refund.gateway_idempotency_key
            or refund.gateway_requested_at is None
        ):
            raise HTTPException(
                409,
                "The saved refund request needs reconciliation.",
            )

        # Commit the retry identity before sending a refund.
        db.commit()

        (
            appointment,
            payment,
            checkout,
            transaction,
            refund,
        ) = lock_refund_context(db, refund_id)

        result = terminal_result(
            db,
            appointment,
            payment,
            transaction,
            refund,
        )

        if result is not None:
            db.commit()
            return result

        if refund.status not in {"processing", "requires_action"}:
            raise HTTPException(
                409,
                "The refund state changed. Reload its details.",
            )

        previous_status = refund.status
        previous_reference = refund.gateway_refund_id

        remote = resolve_booking_refund(
            refund,
            payment,
            appointment,
            checkout,
        )

        remote_status = remote["status"]

        if remote_status == "succeeded":
            ensure_refund_transaction(
                db,
                payment,
                transaction,
                refund,
                create=True,
            )

            payment.payment_status = "refunded"
            refund.status = "succeeded"
            refund.processed_at = utc_now()
            refund.failure_reason = None

            notify_refund_success(
                db,
                appointment,
                transaction,
                refund,
            )

        elif remote_status in {"failed", "canceled"}:
            refund.status = "failed"
            refund.processed_at = utc_now()
            refund.failure_reason = (
                remote.get("failure_reason")
                or f"Stripe refund status: {remote_status}"
            )

        else:
            refund.status = (
                "requires_action"
                if remote_status == "requires_action"
                else "processing"
            )
            refund.processed_at = None
            refund.failure_reason = None

        if (
            refund.status != previous_status
            or refund.gateway_refund_id != previous_reference
        ):
            refund.version += 1

        result = build_result(
            appointment,
            payment,
            refund,
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise