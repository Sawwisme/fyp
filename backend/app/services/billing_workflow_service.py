from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select

from app.models import (
    Appointment,
    Consultation,
    ConsultationBill,
    Notification,
    Payment,
    Pet,
    PetOwner,
    User,
)
from app.schemas.consultation_billing import (
    BillResponse,
    BillingConsultationList,
    BillingConsultationSummary,
)
from app.services.admin_profile_service import get_admin_record
from app.services.consultation_billing_service import (
    lock_billing_context,
    prepare_items,
    utc_now,
)


def list_billing_consultations(
    db,
    current_user,
    q,
    bill_status,
    offset,
    limit,
):
    admin = get_admin_record(db, current_user)

    owner_name = func.coalesce(
        User.full_name,
        PetOwner.contact_name,
        "Owner",
    )

    status = func.coalesce(
        ConsultationBill.status,
        "unbilled",
    )

    statement = (
        select(
            Consultation.consultation_id,
            Appointment.appointment_id,
            Pet.pet_name,
            owner_name.label("owner_name"),
            Consultation.consultation_date,
            ConsultationBill.consultation_bill_id,
            status.label("bill_status"),
            ConsultationBill.total_amount,
        )
        .join(
            Appointment,
            Appointment.appointment_id
            == Consultation.appointment_id,
        )
        .join(Pet, Pet.pet_id == Consultation.pet_id)
        .join(
            PetOwner,
            PetOwner.pet_owner_id == Appointment.pet_owner_id,
        )
        .outerjoin(User, User.user_id == PetOwner.user_id)
        .outerjoin(
            ConsultationBill,
            (
                ConsultationBill.consultation_id
                == Consultation.consultation_id
            )
            & (
                ConsultationBill.clinic_id
                == Consultation.clinic_id
            )
            & (
                ConsultationBill.pet_owner_id
                == Appointment.pet_owner_id
            ),
        )
        .where(
            Consultation.clinic_id == admin.clinic_id,
            Consultation.status == "completed",
            Appointment.status == "completed",
            Appointment.pet_id == Consultation.pet_id,
            Pet.pet_owner_id == Appointment.pet_owner_id,
        )
    )

    keyword = q.strip()

    if keyword:
        statement = statement.where(
            or_(
                Pet.pet_name.contains(keyword, autoescape=True),
                owner_name.contains(keyword, autoescape=True),
            )
        )

    if bill_status is not None:
        statement = statement.where(status == bill_status)

    total = db.scalar(
        select(func.count())
        .select_from(statement.subquery())
    ) or 0

    rows = db.execute(
        statement
        .order_by(
            Consultation.consultation_date.desc(),
            Consultation.consultation_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).mappings().all()

    return BillingConsultationList(
        total=total,
        items=[
            BillingConsultationSummary(**row)
            for row in rows
        ],
    )


def issue_bill(db, current_user, consultation_id, data):
    try:
        _, appointment, bill = lock_billing_context(
            db, current_user, consultation_id
        )

        if bill is None:
            raise HTTPException(
                404,
                "Prepare a draft bill before issuing it.",
            )

        if bill.version != data.expected_version:
            raise HTTPException(
                409,
                "This bill changed. Reload before issuing it.",
            )

        if bill.status != "draft":
            raise HTTPException(
                409,
                "Only a draft bill can be issued.",
            )

        if not 1 <= len(bill.items) <= 50:
            raise HTTPException(
                409,
                "The bill must contain between 1 and 50 items.",
            )

        _, calculated_total = prepare_items(bill.items)

        if (
            calculated_total != bill.total_amount
            or any(
                item.subtotal != item.unit_price * item.quantity
                for item in bill.items
            )
        ):
            raise HTTPException(
                409,
                "The bill amounts need reconciliation.",
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
                "This draft already has a payment record.",
            )

        # Deposit application will be connected in the deposit module.
        # Never silently issue the full amount if a deposit exists.
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
                "The booking deposit must be reconciled and "
                "applied before this bill can be issued.",
            )

        now = utc_now()

        bill.status = (
            "paid"
            if bill.total_amount == Decimal("0.00")
            else "issued"
        )
        bill.issued_at = now
        bill.issued_by_user_id = current_user.user_id
        bill.updated_at = now
        bill.version += 1

        owner_user_id = db.scalar(
            select(PetOwner.user_id)
            .join(User, User.user_id == PetOwner.user_id)
            .where(
                PetOwner.pet_owner_id == bill.pet_owner_id,
                User.role == "pet_owner",
                User.status == "active",
            )
        )

        if owner_user_id is not None:
            db.add(
                Notification(
                    user_id=owner_user_id,
                    event_key=(
                        f"billing:{bill.consultation_bill_id}:issued"
                    ),
                    notification_type="consultation_bill_issued",
                    title="Your consultation bill is ready",
                    message=(
                        f"Bill #{bill.consultation_bill_id} "
                        f"has been issued for "
                        f"RM {bill.total_amount:.2f}. "
                        + (
                            "No payment is required."
                            if bill.total_amount == Decimal("0.00")
                            else "View the bill or contact the clinic "
                                 "for payment."
                        )
                    ),
                    resource_type="consultation_bill",
                    resource_id=bill.consultation_bill_id,
                )
            )

        db.flush()

        result = BillResponse.model_validate(bill)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise