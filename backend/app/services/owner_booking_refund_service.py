from fastapi import HTTPException
from sqlalchemy import select

from app.models import Appointment, Payment, Refund, Transaction
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
        or refund.refund_amount != payment.amount
        or payment.amount != appointment.booking_deposit_amount
    ):
        raise HTTPException(
            409,
            "The deposit refund details need clinic review.",
        )

    return OwnerBookingRefundResponse(
        appointment_id=appointment.appointment_id,
        refund_id=refund.refund_id,
        status=refund.status,
        refund_amount=refund.refund_amount,
        requested_at=refund.requested_at,
        processed_at=refund.processed_at,
    )