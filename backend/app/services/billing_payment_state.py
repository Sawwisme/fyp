from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import (
    BillingStripeSession,
    Clinic,
    Consultation,
    ConsultationBill,
    Payment,
)


def lock_bill_payment_context(
    db,
    bill_id,
    owner_id=None,
):
    location = select(ConsultationBill.clinic_id).where(
        ConsultationBill.consultation_bill_id == bill_id,
    )

    if owner_id is not None:
        location = location.where(
            ConsultationBill.pet_owner_id == owner_id,
        )

    clinic_id = db.scalar(location)

    if clinic_id is None:
        raise HTTPException(404, "Bill not found.")

    # All bill payment changes serialize on the clinic first,
    # matching the existing admin billing services.
    clinic = db.scalar(
        select(Clinic)
        .where(Clinic.clinic_id == clinic_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if clinic is None:
        raise HTTPException(404, "Clinic not found.")

    statement = (
        select(ConsultationBill)
        .where(
            ConsultationBill.consultation_bill_id == bill_id,
            ConsultationBill.clinic_id == clinic_id,
        )
        .options(
            selectinload(ConsultationBill.items),
            selectinload(ConsultationBill.consultation)
            .selectinload(Consultation.appointment),
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if owner_id is not None:
        statement = statement.where(
            ConsultationBill.pet_owner_id == owner_id,
        )

    bill = db.scalar(statement)

    if bill is None:
        raise HTTPException(404, "Bill not found.")

    consultation = bill.consultation
    appointment = consultation.appointment

    if (
        consultation.clinic_id != bill.clinic_id
        or appointment.pet_owner_id != bill.pet_owner_id
        or appointment.pet_id != consultation.pet_id
    ):
        raise HTTPException(
            409,
            "The bill's clinic or ownership needs reconciliation.",
        )

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

    checkouts = db.scalars(
        select(BillingStripeSession)
        .where(
            BillingStripeSession.consultation_bill_id
            == bill.consultation_bill_id,
        )
        .order_by(BillingStripeSession.billing_checkout_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    return clinic, bill, appointment, payments, checkouts