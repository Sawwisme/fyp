from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    Consultation,
    ConsultationBill,
    ConsultationBillDeposit,
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
from app.services.booking_refund_service import (
    build_result,
    ensure_refund_transaction,
    prepare_gateway_request,
    utc_now,
)


def lock_excess_refund_context(db, refund_id):
    location = db.execute(
        select(
            ConsultationBillDeposit.consultation_bill_id,
            Payment.appointment_id,
        )
        .join(
            Payment,
            Payment.payment_id == ConsultationBillDeposit.payment_id,
        )
        .where(
            ConsultationBillDeposit.excess_refund_id == refund_id,
        )
    ).first()

    if location is None or location.appointment_id is None:
        raise HTTPException(404, "Excess deposit refund not found.")

    context = lock_booking_payment_context(
        db,
        location.appointment_id,
    )

    clinic = context[0]
    appointment = context[4]
    payment, checkout = get_saved_attempt(context)

    bill = db.scalar(
        select(ConsultationBill)
        .join(
            Consultation,
            Consultation.consultation_id
            == ConsultationBill.consultation_id,
        )
        .where(
            ConsultationBill.consultation_bill_id
            == location.consultation_bill_id,
            ConsultationBill.clinic_id == clinic.clinic_id,
            ConsultationBill.pet_owner_id == appointment.pet_owner_id,
            Consultation.appointment_id == appointment.appointment_id,
            Consultation.clinic_id == clinic.clinic_id,
            Consultation.status == "completed",
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    allocation = db.scalar(
        select(ConsultationBillDeposit)
        .where(
            ConsultationBillDeposit.consultation_bill_id
            == location.consultation_bill_id,
            ConsultationBillDeposit.payment_id == payment.payment_id,
            ConsultationBillDeposit.excess_refund_id == refund_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if bill is None or allocation is None:
        raise HTTPException(
            409,
            "The excess refund bill allocation is unavailable.",
        )

    transaction = db.scalar(
        select(Transaction)
        .join(
            Refund,
            Refund.transaction_id == Transaction.transaction_id,
        )
        .where(
            Refund.refund_id == refund_id,
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

    refund = db.scalar(
        select(Refund)
        .where(
            Refund.refund_id == refund_id,
            Refund.transaction_id == transaction.transaction_id,
            Refund.refund_purpose == "booking_excess",
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    payer_user_id = db.scalar(
        select(PetOwner.user_id)
        .where(
            PetOwner.pet_owner_id == appointment.pet_owner_id,
        )
    )

    if (
        refund is None
        or appointment.status != "completed"
        or bill.status != "paid"
        or bill.total_amount < 0
        or payment.payment_date is None
        or not payment.receipt_number
        or allocation.deposit_amount != payment.amount
        or allocation.applied_amount
        != min(payment.amount, bill.total_amount)
        or allocation.excess_refund_amount
        != payment.amount - allocation.applied_amount
        or allocation.excess_refund_amount <= 0
        or refund.refund_amount != allocation.excess_refund_amount
        or transaction.order_id is not None
        or transaction.user_id != payer_user_id
        or transaction.transaction_status != "completed"
        or transaction.amount != payment.amount
    ):
        raise HTTPException(
            409,
            "The excess refund does not match the settled bill.",
        )

    bill.deposit_application = allocation

    return appointment, payment, checkout, transaction, refund, allocation


def terminal_excess_result(
    db,
    appointment,
    payment,
    transaction,
    refund,
    allocation,
):
    expected_status = (
        "refunded"
        if allocation.applied_amount == 0
        else "partially_refunded"
    )

    if refund.status == "succeeded":
        if payment.payment_status != expected_status:
            raise HTTPException(
                409,
                "The successful excess refund needs reconciliation.",
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
            "The deposit is unavailable for excess refund processing.",
        )

    if refund.status == "failed":
        return build_result(appointment, payment, refund)

    return None


def notify_excess_refund(db, transaction, refund, allocation):
    if transaction.user_id is None:
        return

    event_key = f"booking-excess-refund:{refund.refund_id}:succeeded"

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
            notification_type="booking_excess_refunded",
            title="Excess deposit refunded",
            message=(
                f"Your unused deposit of RM {refund.refund_amount:.2f} "
                "was refunded. "
                f"RM {allocation.applied_amount:.2f} was applied "
                f"to bill #{allocation.consultation_bill_id}."
            ),
            resource_type="consultation_bill",
            resource_id=allocation.consultation_bill_id,
        )
    )


def process_booking_excess_refund(db, refund_id):
    try:
        (
            appointment,
            payment,
            checkout,
            transaction,
            refund,
            allocation,
        ) = lock_excess_refund_context(db, refund_id)

        result = terminal_excess_result(
            db,
            appointment,
            payment,
            transaction,
            refund,
            allocation,
        )

        if result is not None:
            db.commit()
            return result

        prepare_gateway_request(refund)

        # Persist the refund identity before contacting Stripe.
        db.commit()

        (
            appointment,
            payment,
            checkout,
            transaction,
            refund,
            allocation,
        ) = lock_excess_refund_context(db, refund_id)

        result = terminal_excess_result(
            db,
            appointment,
            payment,
            transaction,
            refund,
            allocation,
        )

        if result is not None:
            db.commit()
            return result

        if refund.status not in {"processing", "requires_action"}:
            raise HTTPException(
                409,
                "The excess refund state changed.",
            )

        previous_status = refund.status
        previous_reference = refund.gateway_refund_id

        remote = resolve_booking_refund(
            refund,
            payment,
            appointment,
            checkout,
            allocation=allocation,
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

            payment.payment_status = (
                "refunded"
                if allocation.applied_amount == 0
                else "partially_refunded"
            )

            refund.status = "succeeded"
            refund.processed_at = utc_now()
            refund.failure_reason = None

            notify_excess_refund(
                db,
                transaction,
                refund,
                allocation,
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