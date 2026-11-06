from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    ConsultationBillDeposit,
    Payment,
    Refund,
    Transaction,
)


def validate_bill_deposit(db, bill, appointment):
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

    allocation = db.scalar(
        select(ConsultationBillDeposit)
        .where(
            ConsultationBillDeposit.consultation_bill_id
            == bill.consultation_bill_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if (
        allocation is None
        and appointment.booking_deposit_amount == 0
        and not payments
    ):
        bill.deposit_application = None
        return

    if allocation is None or len(payments) != 1:
        raise HTTPException(
            409,
            "The bill's deposit allocation needs reconciliation.",
        )

    payment = payments[0]

    if (
        allocation.payment_id != payment.payment_id
        or payment.appointment_id != appointment.appointment_id
        or payment.order_id is not None
        or payment.consultation_bill_id is not None
        or payment.payment_method != "online_banking"
        or payment.payment_date is None
        or not payment.receipt_number
        or payment.amount != appointment.booking_deposit_amount
        or allocation.deposit_amount != payment.amount
        or allocation.applied_amount
        != min(payment.amount, bill.total_amount)
        or allocation.excess_refund_amount
        != payment.amount - allocation.applied_amount
        or allocation.applied_amount < 0
        or allocation.excess_refund_amount < 0
    ):
        raise HTTPException(
            409,
            "The deposit credit does not match this bill.",
        )

    if allocation.excess_refund_amount == 0:
        if (
            allocation.excess_refund_id is not None
            or payment.payment_status != "paid"
        ):
            raise HTTPException(
                409,
                "The applied deposit payment needs reconciliation.",
            )

    else:
        refund = db.scalar(
            select(Refund)
            .join(
                Transaction,
                Transaction.transaction_id == Refund.transaction_id,
            )
            .where(
                Refund.refund_id == allocation.excess_refund_id,
                Transaction.payment_id == payment.payment_id,
                Transaction.transaction_type == "payment",
                Transaction.transaction_status == "completed",
                Transaction.order_id.is_(None),
                Transaction.amount == payment.amount,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if (
            refund is None
            or refund.refund_purpose != "booking_excess"
            or refund.refund_amount != allocation.excess_refund_amount
            or refund.status not in {
                "approved",
                "processing",
                "requires_action",
                "failed",
                "succeeded",
            }
        ):
            raise HTTPException(
                409,
                "The excess deposit refund needs reconciliation.",
            )

        expected_payment_status = "paid"

        if refund.status == "succeeded":
            expected_payment_status = (
                "refunded"
                if allocation.applied_amount == 0
                else "partially_refunded"
            )

        if payment.payment_status != expected_payment_status:
            raise HTTPException(
                409,
                "The deposit payment and excess refund disagree.",
            )

    bill.deposit_application = allocation