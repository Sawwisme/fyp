from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    Appointment,
    Consultation,
    ConsultationBill,
    ConsultationBillDeposit,
    Payment,
    Refund,
    Transaction,
)
from app.schemas.owner_appointments import (
    OwnerBookingRefundResponse,
)
from app.services.pet_service import get_owner_profile


def get_my_booking_refund(db, current_user, appointment_id):
    owner = get_owner_profile(db, current_user)

    appointment = db.scalar(
        select(Appointment)
        .where(
            Appointment.appointment_id == appointment_id,
            Appointment.pet_owner_id == owner.pet_owner_id,
        )
    )

    if appointment is None:
        raise HTTPException(
            404,
            "Appointment not found in your account.",
        )

    records = db.execute(
        select(Refund, Transaction, Payment)
        .select_from(Refund)
        .join(
            Transaction,
            Transaction.transaction_id == Refund.transaction_id,
        )
        .join(
            Payment,
            Payment.payment_id == Transaction.payment_id,
        )
        .where(
            Payment.appointment_id == appointment_id,
            Payment.payment_purpose == "booking_deposit",
            Payment.order_id.is_(None),
            Transaction.order_id.is_(None),
            Transaction.transaction_type == "payment",
        )
        .order_by(Refund.refund_id.desc())
        .limit(2)
    ).all()

    if not records:
        return None

    if len(records) != 1:
        raise HTTPException(
            409,
            "The deposit refund records need clinic review.",
        )

    refund, transaction, payment = records[0]

    if (
        transaction.user_id != current_user.user_id
        or transaction.transaction_status != "completed"
        or transaction.amount != payment.amount
        or payment.amount != appointment.booking_deposit_amount
        or refund.refund_amount <= 0
    ):
        raise HTTPException(
            409,
            "The deposit refund details need clinic review.",
        )

    if refund.refund_purpose == "booking_cancellation":
        if (
            appointment.status != "cancelled"
            or refund.refund_amount != payment.amount
        ):
            raise HTTPException(
                409,
                "The cancellation refund needs clinic review.",
            )

        successful_payment_status = "refunded"

    elif refund.refund_purpose == "booking_excess":
        allocation = db.scalar(
            select(ConsultationBillDeposit)
            .join(
                ConsultationBill,
                ConsultationBill.consultation_bill_id
                == ConsultationBillDeposit.consultation_bill_id,
            )
            .join(
                Consultation,
                Consultation.consultation_id
                == ConsultationBill.consultation_id,
            )
            .where(
                ConsultationBillDeposit.payment_id == payment.payment_id,
                ConsultationBillDeposit.excess_refund_id
                == refund.refund_id,
                ConsultationBill.pet_owner_id == owner.pet_owner_id,
                ConsultationBill.status == "paid",
                Consultation.appointment_id == appointment_id,
                Consultation.clinic_id == ConsultationBill.clinic_id,
                Consultation.status == "completed",
            )
        )

        if (
            allocation is None
            or appointment.status != "completed"
            or allocation.deposit_amount != payment.amount
            or allocation.applied_amount < 0
            or allocation.excess_refund_amount != refund.refund_amount
            or allocation.applied_amount
            + allocation.excess_refund_amount
            != payment.amount
        ):
            raise HTTPException(
                409,
                "The excess refund needs clinic review.",
            )

        successful_payment_status = (
            "refunded"
            if allocation.applied_amount == 0
            else "partially_refunded"
        )

    else:
        raise HTTPException(
            409,
            "The refund purpose needs clinic review.",
        )

    expected_payment_status = (
        successful_payment_status
        if refund.status == "succeeded"
        else "paid"
    )

    if payment.payment_status != expected_payment_status:
        raise HTTPException(
            409,
            "The deposit payment and refund status disagree.",
        )

    return OwnerBookingRefundResponse(
        appointment_id=appointment.appointment_id,
        refund_id=refund.refund_id,
        refund_purpose=refund.refund_purpose,
        status=refund.status,
        refund_amount=refund.refund_amount,
        requested_at=refund.requested_at,
        processed_at=refund.processed_at,
    )