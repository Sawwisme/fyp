from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Appointment,
    Clinic,
    Consultation,
    ConsultationBill,
    ConsultationBillItem,
    Payment,
    Pet,
)
from app.schemas.consultation_billing import BillResponse
from app.services.admin_profile_service import get_admin_record


MAX_AMOUNT = Decimal("99999999.99")


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def lock_billing_context(db, current_user, consultation_id):
    admin = get_admin_record(db, current_user)

    clinic = db.scalar(
        select(Clinic)
        .where(
            Clinic.clinic_id == admin.clinic_id,
            Clinic.status == "active",
        )
        .with_for_update()
    )

    if clinic is None:
        raise HTTPException(403, "Your clinic is unavailable.")

    consultation = db.scalar(
        select(Consultation)
        .where(
            Consultation.consultation_id == consultation_id,
            Consultation.clinic_id == clinic.clinic_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if consultation is None:
        raise HTTPException(404, "Consultation not found.")

    if consultation.status != "completed":
        raise HTTPException(
            409,
            "Complete the consultation before preparing its bill.",
        )

    appointment = db.scalar(
        select(Appointment)
        .where(
            Appointment.appointment_id
            == consultation.appointment_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if (
        appointment is None
        or appointment.status != "completed"
        or appointment.pet_id != consultation.pet_id
    ):
        raise HTTPException(
            409,
            "The consultation and appointment need reconciliation.",
        )

    pet_owner_id = db.scalar(
        select(Pet.pet_owner_id)
        .where(Pet.pet_id == consultation.pet_id)
    )

    if pet_owner_id != appointment.pet_owner_id:
        raise HTTPException(
            409,
            "The patient ownership record needs reconciliation.",
        )

    bill = db.scalar(
        select(ConsultationBill)
        .where(
            ConsultationBill.consultation_id == consultation_id,
        )
        .options(selectinload(ConsultationBill.items))
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if bill is not None and (
        bill.clinic_id != clinic.clinic_id
        or bill.pet_owner_id != appointment.pet_owner_id
    ):
        raise HTTPException(
            409,
            "The existing bill needs reconciliation.",
        )

    return consultation, appointment, bill


def prepare_items(items):
    total = Decimal("0.00")
    prepared = []

    for item in items:
        price = item.unit_price.quantize(Decimal("0.01"))
        subtotal = price * item.quantity

        if subtotal > MAX_AMOUNT:
            raise HTTPException(
                422,
                "A bill item exceeds the supported amount.",
            )

        total += subtotal

        if total > MAX_AMOUNT:
            raise HTTPException(
                422,
                "The bill total exceeds the supported amount.",
            )

        prepared.append(
            ConsultationBillItem(
                item_type=item.item_type,
                description=item.description,
                quantity=item.quantity,
                unit_price=price,
                subtotal=subtotal,
            )
        )

    return prepared, total


def create_draft(db: Session, current_user, consultation_id, data):
    try:
        consultation, appointment, bill = lock_billing_context(
            db, current_user, consultation_id
        )

        # Repeated creation returns the existing bill.
        # It never overwrites saved charges.
        if bill is not None:
            result = BillResponse.model_validate(bill)
            db.commit()
            return result

        items, total = prepare_items(data.items)
        now = utc_now()

        bill = ConsultationBill(
            consultation_id=consultation.consultation_id,
            clinic_id=consultation.clinic_id,
            pet_owner_id=appointment.pet_owner_id,
            status="draft",
            total_amount=total,
            version=1,
            created_by_user_id=current_user.user_id,
            created_at=now,
            updated_at=now,
            items=items,
        )

        db.add(bill)
        db.flush()

        result = BillResponse.model_validate(bill)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def get_bill(db: Session, current_user, consultation_id):
    try:
        _, _, bill = lock_billing_context(
            db, current_user, consultation_id
        )

        if bill is None:
            raise HTTPException(404, "No bill has been prepared yet.")

        result = BillResponse.model_validate(bill)
        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def update_draft(db: Session, current_user, consultation_id, data):
    try:
        _, _, bill = lock_billing_context(
            db, current_user, consultation_id
        )

        if bill is None:
            raise HTTPException(404, "Bill not found.")

        if bill.version != data.expected_version:
            raise HTTPException(
                409,
                "This bill changed. Reload before saving.",
            )

        if bill.status != "draft":
            raise HTTPException(
                409,
                "Only draft bills can be edited.",
            )

        active_payment = db.scalar(
            select(Payment.payment_id)
            .where(
                Payment.consultation_bill_id
                == bill.consultation_bill_id,
                Payment.payment_status.not_in([
                    "failed",
                    "cancelled",
                    "expired",
                ]),
            )
            .limit(1)
        )

        if active_payment is not None:
            raise HTTPException(
                409,
                "This bill has a payment record and cannot be edited.",
            )

        items, total = prepare_items(data.items)

        bill.items = items
        bill.total_amount = total
        bill.version += 1
        bill.updated_at = utc_now()

        db.flush()

        result = BillResponse.model_validate(bill)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise