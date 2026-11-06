from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, Payment, Refund, Transaction, User, OrderStatusHistory
from app.schemas.clinic_refunds import ClinicRefundReview, CashRefundConfirm
from app.services.admin_profile_service import get_admin_record
from app.services.order_reservation_service import _lock_order
from app.services.shop_refund_service import build_refund_response
from app.services.shop_notification_service import notify_refund_status


def _get_clinic_order(db, current_user, order_id):
    admin = get_admin_record(db, current_user)

    # Check clinic ownership before acquiring order locks.
    scoped_id = db.scalar(
        select(Order.order_id).where(
            Order.order_id == order_id,
            Order.clinic_id == admin.clinic_id,
            Order.checkout_key.is_not(None),
        )
    )

    if scoped_id is None:
        raise HTTPException(404, "Order not found.")

    order = _lock_order(db, order_id)

    if order is None or order.clinic_id != admin.clinic_id:
        raise HTTPException(404, "Order not found.")

    return admin, order


def list_order_refunds(
    db: Session,
    current_user: User,
    order_id: int,
):
    try:
        _, order = _get_clinic_order(
            db, current_user, order_id
        )

        refunds = db.scalars(
            select(Refund)
            .join(
                Transaction,
                Transaction.transaction_id
                == Refund.transaction_id,
            )
            .where(Transaction.order_id == order.order_id)
            .order_by(Refund.refund_id.desc())
        ).all()

        result = [
            build_refund_response(refund, order.order_id)
            for refund in refunds
        ]

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def review_refund(
    db: Session,
    current_user: User,
    order_id: int,
    refund_id: int,
    data: ClinicRefundReview,
):
    try:
        admin, order = _get_clinic_order(
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

        if refund.version != data.expected_version:
            raise HTTPException(
                409,
                "This refund changed. Reload before reviewing it.",
            )

        if refund.status != "pending":
            raise HTTPException(
                409,
                "This refund request has already been reviewed.",
            )

        if data.decision == "approved":
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
                or payment.payment_status != "paid"
                or payment.payment_date is None
                or payment.payment_method
                not in {"cash", "online_banking", "card"}
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
                    "The payment must be reconciled before approval.",
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
                    "Another refund request already exists for this order.",
                )

        refund.status = data.decision
        refund.review_notes = data.review_notes
        refund.reviewed_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        )

        refund.approved_by = (
            admin.clinic_administrator_id
            if data.decision == "approved"
            else None
        )

        refund.version += 1

        # Approval does not mean that money has been returned.
        refund.processed_at = None

        notify_refund_status(
            db,
            order,
            refund,
        )

        db.flush()
        result = build_refund_response(
            refund, order.order_id
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise

def confirm_cash_refund(
    db: Session,
    current_user: User,
    order_id: int,
    refund_id: int,
    data: CashRefundConfirm,
):
    try:
        if not data.cash_returned:
            raise HTTPException(
                422,
                "Confirm that the cash has actually been returned.",
            )

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

        if refund.version != data.expected_version:
            raise HTTPException(
                409,
                "This refund changed. Reload its details.",
            )

        if refund.status != "approved":
            raise HTTPException(
                409,
                "Only an approved refund can be confirmed. "
                "This refund may already have been processed.",
            )

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
            or payment.payment_method != "cash"
            or payment.payment_status != "paid"
            or payment.payment_date is None
            or order.shipping_method != "pickup"
            or order.order_status != "completed"
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
                "This is not an eligible paid cash-pickup order.",
            )

        existing_refund_transaction = db.scalar(
            select(Transaction.transaction_id)
            .where(
                Transaction.payment_id == payment.payment_id,
                Transaction.transaction_type == "refund",
            )
            .limit(1)
        )

        if existing_refund_transaction is not None:
            raise HTTPException(
                409,
                "A refund transaction already exists for this payment.",
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
                "Another refund request needs to be reconciled.",
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)

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
        order.order_status = "refunded"
        order.version += 1

        refund.status = "succeeded"
        refund.processed_at = now
        refund.version += 1

        approval_notes = refund.review_notes or ""
        refund.review_notes = (
            f"{approval_notes}\n\n"
            f"Cash returned by staff user "
            f"#{current_user.user_id}: {data.notes}"
        ).strip()

        db.add(
            OrderStatusHistory(
                order_id=order.order_id,
                changed_by_user_id=current_user.user_id,
                previous_status=previous_status,
                new_status="refunded",
                resulting_version=order.version,
                notes=(
                    f"Cash refund #{refund.refund_id} confirmed. "
                    "Cash returned to the owner."
                ),
                created_at=now,
            )
        )

        notify_refund_status(
            db,
            order,
            refund,
            cash=True,
        )

        db.flush()

        result = build_refund_response(
            refund, order.order_id
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise