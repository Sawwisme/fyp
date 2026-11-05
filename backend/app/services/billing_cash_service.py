from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Notification, Payment, PetOwner, Transaction
from app.schemas.consultation_billing import (
    BillCashReceipt,
    BillResponse,
    BillPaymentSummary,
)
from app.services.consultation_billing_service import (
    lock_billing_context,
    prepare_items,
    utc_now,
)


def receipt_response(bill, payment):
    return BillCashReceipt(
        bill=BillResponse.model_validate(bill),
        payment_id=payment.payment_id,
        receipt_number=payment.receipt_number,
        amount=payment.amount,
        payment_date=payment.payment_date,
    )


def collect_cash(db, current_user, consultation_id, data):
    try:
        if not data.cash_received:
            raise HTTPException(
                422,
                "Confirm that the full cash amount was received.",
            )

        _, appointment, bill = lock_billing_context(
            db, current_user, consultation_id
        )

        if bill is None:
            raise HTTPException(404, "Bill not found.")

        payments = db.scalars(
            select(Payment)
            .where(
                Payment.consultation_bill_id
                == bill.consultation_bill_id,
            )
            .order_by(Payment.payment_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        ).all()

        payer_user_id = db.scalar(
            select(PetOwner.user_id)
            .where(
                PetOwner.pet_owner_id == bill.pet_owner_id,
            )
        )

        paid = [
            payment
            for payment in payments
            if payment.payment_status == "paid"
        ]

        # A retry can return the original receipt, without
        # creating another payment or transaction.
        if bill.status == "paid":
            if len(paid) != 1:
                raise HTTPException(
                    409,
                    "This bill has no single cash receipt to return.",
                )

            payment = paid[0]

            transaction = db.scalar(
                select(Transaction)
                .where(
                    Transaction.payment_id == payment.payment_id,
                    Transaction.transaction_type == "payment",
                )
                .with_for_update()
            )

            if (
                payment.payment_method != "cash"
                or payment.payment_purpose != "consultation_balance"
                or payment.appointment_id != appointment.appointment_id
                or payment.order_id is not None
                or payment.amount != bill.total_amount
                or data.expected_amount != payment.amount
                or not payment.receipt_number
                or payment.payment_date is None
                or transaction is None
                or transaction.user_id != payer_user_id
                or transaction.order_id is not None
                or transaction.amount != payment.amount
                or transaction.transaction_status != "completed"
            ):
                raise HTTPException(
                    409,
                    "This bill is already settled or needs reconciliation.",
                )

            result = receipt_response(bill, payment)
            db.commit()
            return result

        if bill.version != data.expected_version:
            raise HTTPException(
                409,
                "This bill changed. Reload before collecting payment.",
            )

        if (
            bill.status != "issued"
            or bill.total_amount <= 0
            or bill.total_amount != data.expected_amount
        ):
            raise HTTPException(
                409,
                "An issued bill with the matching unpaid amount is required.",
            )

        if any(
            payment.payment_status not in {
                "failed",
                "cancelled",
                "expired",
            }
            for payment in payments
        ):
            raise HTTPException(
                409,
                "Another payment is pending or already recorded. "
                "Resolve it before accepting cash.",
            )

        deposit = db.scalar(
            select(Payment.payment_id)
            .where(
                Payment.appointment_id == appointment.appointment_id,
                Payment.order_id.is_(None),
                Payment.payment_purpose == "booking_deposit",
                Payment.payment_status.in_(["pending", "paid"]),
            )
            .limit(1)
        )

        if deposit is not None:
            raise HTTPException(
                409,
                "The appointment deposit must be reconciled "
                "before collecting the balance.",
            )

        _, calculated_total = prepare_items(bill.items)

        if (
            not bill.items
            or calculated_total != bill.total_amount
            or any(
                item.subtotal != item.quantity * item.unit_price
                for item in bill.items
            )
        ):
            raise HTTPException(
                409,
                "The bill amounts need reconciliation.",
            )

        now = utc_now()

        payment = Payment(
            order_id=None,
            appointment_id=appointment.appointment_id,
            consultation_bill_id=bill.consultation_bill_id,
            payment_purpose="consultation_balance",
            payment_method="cash",
            payment_status="paid",
            amount=bill.total_amount,
            payment_date=now,
            receipt_number=f"BILL-CASH-{uuid4().hex}",
            received_by_user_id=current_user.user_id,
            staff_notes=data.notes or None,
        )

        db.add(payment)
        db.flush()

        db.add(
            Transaction(
                user_id=payer_user_id,
                order_id=None,
                payment_id=payment.payment_id,
                transaction_type="payment",
                amount=payment.amount,
                transaction_status="completed",
                transaction_date=now,
            )
        )

        bill.status = "paid"
        bill.version += 1
        bill.updated_at = now

        if payer_user_id is not None:
            db.add(
                Notification(
                    user_id=payer_user_id,
                    event_key=(
                        f"billing:{bill.consultation_bill_id}:paid"
                    ),
                    notification_type="consultation_bill_paid",
                    title="Consultation payment received",
                    message=(
                        f"The clinic received "
                        f"RM {payment.amount:.2f} in cash "
                        f"for bill #{bill.consultation_bill_id}."
                    ),
                    resource_type="consultation_bill",
                    resource_id=bill.consultation_bill_id,
                )
            )

        db.flush()

        result = receipt_response(bill, payment)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise

def list_bill_payments(db, current_user, consultation_id):
    try:
        _, _, bill = lock_billing_context(
            db, current_user, consultation_id
        )

        if bill is None:
            raise HTTPException(404, "Bill not found.")

        payments = db.scalars(
            select(Payment)
            .where(
                Payment.consultation_bill_id
                == bill.consultation_bill_id,
            )
            .order_by(Payment.payment_id.desc())
        ).all()

        result = [
            BillPaymentSummary.model_validate(payment)
            for payment in payments
        ]

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise