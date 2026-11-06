from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Payment, Refund, Transaction, User
from app.schemas.shop_refunds import (
    ShopRefundCreate,
    ShopRefundResponse,
)
from app.services.order_reservation_service import _lock_order
from app.services.pet_service import get_owner_profile
from app.services.shop_notification_service import notify_shop_event


def build_refund_response(refund, order_id):
    return ShopRefundResponse(
        refund_id=refund.refund_id,
        order_id=order_id,
        refund_amount=refund.refund_amount,
        reason=refund.reason,
        status=refund.status,
        version=refund.version,
        review_notes=refund.review_notes,
        requested_at=refund.requested_at,
        reviewed_at=refund.reviewed_at,
        processed_at=refund.processed_at,
        stock_reviewed_at=refund.stock_reviewed_at,
        stock_return_items=refund.stock_return_items,
    )


def _find_refunds(db, order_id):
    return db.scalars(
        select(Refund)
        .join(
            Transaction,
            Transaction.transaction_id == Refund.transaction_id,
        )
        .where(Transaction.order_id == order_id)
        .order_by(Refund.refund_id.desc())
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()


def request_my_refund(
    db: Session,
    current_user: User,
    order_id: int,
    data: ShopRefundCreate,
):
    try:
        owner = get_owner_profile(db, current_user)

        # Use the same clinic/order lock order as payment processing.
        order = _lock_order(
            db,
            order_id,
            owner.pet_owner_id,
        )

        if order is None:
            raise HTTPException(404, "Order not found.")

        payments = db.scalars(
            select(Payment)
            .where(Payment.order_id == order_id)
            .order_by(Payment.payment_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        ).all()

        existing = _find_refunds(db, order_id)

        # Repeated submissions return the existing request.
        # A rejected request may be submitted again.
        blocking = next(
            (
                refund
                for refund in existing
                if refund.status != "rejected"
            ),
            None,
        )

        if blocking is not None:
            result = build_refund_response(blocking, order_id)
            db.commit()
            return result

        paid = [
            payment
            for payment in payments
            if payment.payment_status == "paid"
        ]

        if len(paid) != 1:
            raise HTTPException(
                409,
                "This order has no eligible verified payment. "
                "Contact the clinic if payment was deducted.",
            )

        payment = paid[0]

        if (
            payment.payment_method not in {"cash", "online_banking", "card"}
            or payment.payment_date is None
            or payment.amount != order.total_amount
            or payment.amount <= 0
        ):
            raise HTTPException(
                409,
                "The payment needs to be reviewed by the clinic.",
            )

        transactions = db.scalars(
            select(Transaction)
            .where(
                Transaction.order_id == order_id,
                Transaction.payment_id == payment.payment_id,
                Transaction.transaction_type == "payment",
                Transaction.transaction_status == "completed",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        ).all()

        if len(transactions) != 1:
            raise HTTPException(
                409,
                "The payment record needs to be reviewed by the clinic.",
            )

        transaction = transactions[0]

        if (
            transaction.user_id != current_user.user_id
            or transaction.amount != payment.amount
        ):
            raise HTTPException(
                409,
                "The payment record does not match this order.",
            )

        refund = Refund(
            transaction_id=transaction.transaction_id,
            requested_by=current_user.user_id,
            refund_amount=payment.amount,
            reason=data.reason,
            status="pending",
            version=1,
            requested_at=datetime.now(timezone.utc).replace(
                tzinfo=None
            ),
        )

        db.add(refund)
        db.flush()

        notify_shop_event(
            db,
            order,
            event_key=f"shop:refund:{refund.refund_id}:requested",
            title="Refund request received",
            message=(
                f"The owner requested a refund for "
                f"order #{order.order_id}. "
                "Open the order to review the reason."
            ),
            include_owner=False,
            include_admins=True,
        )

        result = build_refund_response(refund, order_id)
        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def list_my_order_refunds(
    db: Session,
    current_user: User,
    order_id: int,
):
    try:
        owner = get_owner_profile(db, current_user)

        order = _lock_order(
            db,
            order_id,
            owner.pet_owner_id,
        )

        if order is None:
            raise HTTPException(404, "Order not found.")

        result = [
            build_refund_response(refund, order_id)
            for refund in _find_refunds(db, order_id)
        ]

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise