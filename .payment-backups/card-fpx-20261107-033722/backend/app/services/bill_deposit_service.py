from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select

from app.models import (
    BookingStripeSession,
    ConsultationBillDeposit,
    Payment,
    PetOwner,
    Refund,
    Transaction,
)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def apply_booking_deposit(
    db,
    current_user,
    appointment,
    bill,
):
    """
    Called while issuing a draft bill, with its clinic,
    appointment and bill already locked.

    The caller commits the allocation, excess refund request,
    and issued bill together.
    """
    if bill.deposit_application is not None:
        raise HTTPException(
            409,
            "This draft already has a deposit allocation.",
        )

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
            "The booking deposit records need reconciliation.",
        )

    payment = payments[0]

    if (
        appointment.status != "completed"
        or not appointment.booking_request_id
        or appointment.booking_deposit_amount <= 0
        or payment.payment_status != "paid"
        or payment.payment_method != "online_banking"
        or payment.order_id is not None
        or payment.consultation_bill_id is not None
        or payment.amount != appointment.booking_deposit_amount
        or payment.payment_date is None
        or not payment.receipt_number
        or not isinstance(payment.gateway_reference, str)
        or not payment.gateway_reference.startswith("pi_")
        or bill.total_amount < 0
    ):
        raise HTTPException(
            409,
            "The paid booking deposit must be reconciled "
            "before issuing this bill.",
        )

    checkout_records = db.scalars(
        select(BookingStripeSession)
        .where(
            BookingStripeSession.appointment_id
            == appointment.appointment_id,
        )
        .order_by(BookingStripeSession.booking_checkout_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    if len(checkout_records) != 1:
        raise HTTPException(
            409,
            "The deposit checkout records need reconciliation.",
        )

    checkout = checkout_records[0]

    if (
        checkout.payment_id != payment.payment_id
        or checkout.session_status != "complete"
        or checkout.currency != "myr"
        or checkout.amount_cents != int(payment.amount * 100)
        or not checkout.stripe_session_id
        or not checkout.stripe_session_id.startswith("cs_test_")
    ):
        raise HTTPException(
            409,
            "The deposit has no matching verified checkout.",
        )

    existing_allocation = db.scalar(
        select(ConsultationBillDeposit)
        .where(
            or_(
                ConsultationBillDeposit.consultation_bill_id
                == bill.consultation_bill_id,
                ConsultationBillDeposit.payment_id
                == payment.payment_id,
            )
        )
        .with_for_update()
    )

    if existing_allocation is not None:
        raise HTTPException(
            409,
            "This deposit is already allocated to a bill.",
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
            "The deposit transaction does not match this bill.",
        )

    existing_refund = db.scalar(
        select(Refund.refund_id)
        .where(
            Refund.transaction_id == transaction.transaction_id,
        )
        .limit(1)
        .with_for_update()
    )

    if existing_refund is not None:
        raise HTTPException(
            409,
            "This deposit already has a refund request. "
            "Reconcile it before applying the deposit.",
        )

    applied_amount = min(
        payment.amount,
        bill.total_amount,
    )

    excess_amount = payment.amount - applied_amount
    now = utc_now()

    allocation = ConsultationBillDeposit(
        consultation_bill_id=bill.consultation_bill_id,
        payment_id=payment.payment_id,
        deposit_amount=payment.amount,
        applied_amount=applied_amount,
        excess_refund_amount=excess_amount,
        created_at=now,
    )

    if excess_amount > 0:
        excess_refund = Refund(
            transaction_id=transaction.transaction_id,
            requested_by=current_user.user_id,
            approved_by=None,
            refund_purpose="booking_excess",
            refund_amount=excess_amount,
            reason=(
                "Unused booking deposit for consultation bill "
                f"#{bill.consultation_bill_id}."
            ),
            status="approved",
            version=1,
            review_notes=(
                "Automatically approved because the booking "
                "deposit exceeds the final consultation charges."
            ),
            reviewed_at=now,
            requested_at=now,
            gateway_idempotency_key=str(uuid4()),
            gateway_requested_at=None,
        )

        db.add(excess_refund)
        db.flush()

        allocation.excess_refund = excess_refund

    bill.deposit_application = allocation

    db.add(allocation)
    db.flush()

    return allocation