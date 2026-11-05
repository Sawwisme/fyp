from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models import (
    Appointment,
    Clinic,
    Consultation,
    ConsultationBill,
    Payment,
    Pet,
)
from app.schemas.consultation_billing import (
    BillPaymentSummary,
    BillResponse,
)
from app.schemas.owner_billing import (
    OwnerBillDetail,
    OwnerBillList,
    OwnerBillSummary,
)
from app.services.pet_service import get_owner_profile


def owner_bill_conditions(owner_id):
    return (
        ConsultationBill.pet_owner_id == owner_id,
        Appointment.pet_owner_id == owner_id,
        ConsultationBill.clinic_id == Consultation.clinic_id,
        Appointment.pet_id == Consultation.pet_id,
        ConsultationBill.issued_at.is_not(None),
        ConsultationBill.status.in_([
            "issued",
            "paid",
            "void",
        ]),
    )


def list_my_bills(
    db,
    current_user,
    bill_status,
    offset,
    limit,
):
    owner = get_owner_profile(db, current_user)

    statement = (
        select(
            ConsultationBill.consultation_bill_id,
            ConsultationBill.consultation_id,
            Clinic.clinic_name,
            Pet.pet_name,
            Consultation.consultation_date,
            ConsultationBill.issued_at,
            ConsultationBill.status,
            ConsultationBill.total_amount,
        )
        .join(
            Consultation,
            Consultation.consultation_id
            == ConsultationBill.consultation_id,
        )
        .join(
            Appointment,
            Appointment.appointment_id
            == Consultation.appointment_id,
        )
        .join(
            Clinic,
            Clinic.clinic_id == ConsultationBill.clinic_id,
        )
        .join(
            Pet,
            Pet.pet_id == Consultation.pet_id,
        )
        .where(*owner_bill_conditions(owner.pet_owner_id))
    )

    if bill_status is not None:
        statement = statement.where(
            ConsultationBill.status == bill_status,
        )

    total = db.scalar(
        select(func.count())
        .select_from(statement.subquery())
    ) or 0

    rows = db.execute(
        statement
        .order_by(
            ConsultationBill.issued_at.desc(),
            ConsultationBill.consultation_bill_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).mappings().all()

    return OwnerBillList(
        total=total,
        items=[
            OwnerBillSummary(**row)
            for row in rows
        ],
    )


def get_my_bill(db, current_user, bill_id):
    owner = get_owner_profile(db, current_user)

    bill = db.scalar(
        select(ConsultationBill)
        .join(
            Consultation,
            Consultation.consultation_id
            == ConsultationBill.consultation_id,
        )
        .join(
            Appointment,
            Appointment.appointment_id
            == Consultation.appointment_id,
        )
        .where(
            ConsultationBill.consultation_bill_id == bill_id,
            *owner_bill_conditions(owner.pet_owner_id),
        )
        .options(
            selectinload(ConsultationBill.items),
            selectinload(ConsultationBill.clinic),
            selectinload(ConsultationBill.consultation)
            .selectinload(Consultation.pet),
            selectinload(ConsultationBill.consultation)
            .selectinload(Consultation.appointment),
        )
    )

    if bill is None:
        raise HTTPException(404, "Bill not found.")

    consultation = bill.consultation
    appointment = consultation.appointment

    payments = db.scalars(
        select(Payment)
        .where(
            Payment.consultation_bill_id
            == bill.consultation_bill_id,
            Payment.appointment_id == appointment.appointment_id,
            Payment.order_id.is_(None),
            Payment.payment_purpose == "consultation_balance",
        )
        .order_by(Payment.payment_id.desc())
    ).all()

    return OwnerBillDetail(
        bill=BillResponse.model_validate(bill),
        appointment_id=appointment.appointment_id,
        clinic_name=bill.clinic.clinic_name,
        clinic_address=bill.clinic.address,
        clinic_phone=bill.clinic.phone_number,
        pet_name=consultation.pet.pet_name,
        payments=[
            BillPaymentSummary.model_validate(payment)
            for payment in payments
        ],
    )