from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    OrderStatusHistory,
    Payment,
    Refund,
    Transaction,
)
from app.services.clinic_refund_service import _get_clinic_order
from app.services.shop_refund_service import build_refund_response
from app.services.stripe_refund_gateway import resolve_stripe_refund
from app.services.order_reservation_service import _lock_order


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _lock_context(db, current_user, order_id, refund_id):
    if current_user is None:
        # Internal worker: continue an existing refund.
        order = _lock_order(db, order_id)

        if order is None:
            raise HTTPException(404, "Order not found.")
    else:
        _, order = _get_clinic_order(
            db, current_user, order_id
        )

    payments = db.scalars(
        select(Payment)
        .where(Payment.order_id == order.order_id)
        .order_by(Payment.payment_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    transaction = db.scalar(
        select(Transaction)
        .join(
            Refund,
            Refund.transaction_id
            == Transaction.transaction_id,
        )
        .where(
            Refund.refund_id == refund_id,
            Transaction.order_id == order.order_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if transaction is None:
        raise HTTPException(404, "Refund request not found.")

    refund = db.scalar(
        select(Refund)
        .where(
            Refund.refund_id == refund_id,
            Refund.transaction_id
            == transaction.transaction_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if refund is None:
        raise HTTPException(404, "Refund request not found.")

    payment = next(
        (
            item
            for item in payments
            if item.payment_id == transaction.payment_id
        ),
        None,
    )

    if (
        payment is None
        or payment.payment_method != "online_banking"
        or payment.payment_date is None
        or transaction.transaction_type != "payment"
        or transaction.transaction_status != "completed"
        or refund.requested_by != transaction.user_id
        or refund.refund_amount != transaction.amount
        or refund.refund_amount != payment.amount
        or refund.refund_amount != order.total_amount
        or refund.refund_amount <= 0
    ):
        raise HTTPException(
            409,
            "The online payment needs reconciliation.",
        )

    other_refund = db.scalar(
        select(Refund.refund_id)
        .join(
            Transaction,
            Transaction.transaction_id
            == Refund.transaction_id,
        )
        .where(
            Transaction.order_id == order.order_id,
            Refund.refund_id != refund.refund_id,
            Refund.status != "rejected",
        )
        .limit(1)
    )

    if other_refund is not None:
        raise HTTPException(
            409,
            "Another refund request needs reconciliation.",
        )

    return order, payment, transaction, refund


def process_online_refund(
    db: Session,
    current_user,
    order_id: int,
    refund_id: int,
    data,
):
    try:
        order, payment, transaction, refund = _lock_context(
            db, current_user, order_id, refund_id
        )

        if refund.status == "succeeded":
            result = build_refund_response(
                refund, order.order_id
            )
            db.commit()
            return result

        if current_user is None and (
            refund.status not in {
                "processing",
                "requires_action",
            }
            or not refund.gateway_idempotency_key
            or refund.gateway_requested_at is None
        ):
            raise HTTPException(
                409,
                "Automatic syncing only continues refunds "
                "already submitted for processing.",
            )

        if refund.version != data.expected_version:
            raise HTTPException(
                409,
                "This refund changed. Reload before continuing.",
            )

        if (
            refund.status not in {
                "approved",
                "processing",
                "requires_action",
                "failed",
            }
            or payment.payment_status != "paid"
        ):
            raise HTTPException(
                409,
                "An approved, paid online refund is required.",
            )

        if refund.gateway_idempotency_key is None:
            if (
                refund.status != "approved"
                or refund.gateway_refund_id is not None
                or refund.gateway_requested_at is not None
            ):
                raise HTTPException(
                    409,
                    "The refund request needs reconciliation.",
                )

            refund.gateway_idempotency_key = str(uuid4())
            refund.gateway_requested_at = utc_now()
            refund.status = "processing"
            refund.version += 1

        elif refund.gateway_requested_at is None:
            raise HTTPException(
                409,
                "The refund request timestamp is missing.",
            )

        # Save the retry identity before any Stripe request.
        db.commit()

        # Reacquire locks and recheck the state after committing.
        order, payment, transaction, refund = _lock_context(
            db, current_user, order_id, refund_id
        )

        if refund.status == "succeeded":
            result = build_refund_response(
                refund, order.order_id
            )
            db.commit()
            return result

        if (
            refund.status not in {
                "processing",
                "requires_action",
                "failed",
            }
            or payment.payment_status != "paid"
        ):
            raise HTTPException(
                409,
                "The refund state changed. Reload its details.",
            )

        remote = resolve_stripe_refund(
            refund, payment, order
        )

        remote_status = remote["status"]
        now = utc_now()

        if remote_status == "succeeded":
            existing = db.scalar(
                select(Transaction)
                .where(
                    Transaction.payment_id == payment.payment_id,
                    Transaction.transaction_type == "refund",
                )
                .with_for_update()
            )

            if existing is not None:
                if (
                    existing.order_id != order.order_id
                    or existing.user_id != transaction.user_id
                    or existing.amount != refund.refund_amount
                    or existing.transaction_status != "completed"
                ):
                    raise HTTPException(
                        409,
                        "The refund transaction needs reconciliation.",
                    )
            else:
                db.add(
                    Transaction(
                        user_id=transaction.user_id,
                        order_id=order.order_id,
                        payment_id=payment.payment_id,
                        transaction_type="refund",
                        amount=refund.refund_amount,
                        transaction_status="completed",
                        transaction_date=now,
                    )
                )

            previous_status = order.order_status

            payment.payment_status = "refunded"

            if previous_status != "refunded":
                order.order_status = "refunded"
                order.version += 1

                db.add(
                    OrderStatusHistory(
                        order_id=order.order_id,
                        changed_by_user_id=(
                            current_user.user_id
                            if current_user is not None
                            else None
                        ),
                        previous_status=previous_status,
                        new_status="refunded",
                        resulting_version=order.version,
                        notes=(
                            f"Stripe refund #{refund.refund_id} "
                            "verified as successful."
                        ),
                        created_at=now,
                    )
                )

            refund.status = "succeeded"
            refund.processed_at = now
            refund.failure_reason = None

        elif remote_status in {"failed", "canceled"}:
            refund.status = "failed"
            refund.processed_at = now
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

        refund.version += 1
        db.flush()

        result = build_refund_response(
            refund, order.order_id
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise