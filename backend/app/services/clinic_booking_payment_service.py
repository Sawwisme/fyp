from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Clinic, User
from app.schemas.clinic_booking_payment import (
    BookingPaymentSettingsResponse,
    BookingPaymentSettingsUpdate,
)
from app.services.admin_profile_service import get_admin_record


def build_settings(clinic: Clinic):
    return BookingPaymentSettingsResponse(
        clinic_id=clinic.clinic_id,
        deposit_amount=clinic.booking_deposit_amount,
        version=clinic.booking_payment_version,
    )


def get_my_settings(
    db: Session,
    current_user: User,
):
    administrator = get_admin_record(db, current_user)

    clinic = db.scalar(
        select(Clinic)
        .where(
            Clinic.clinic_id == administrator.clinic_id,
            Clinic.status == "active",
        )
        .execution_options(populate_existing=True)
    )

    if clinic is None:
        raise HTTPException(403, "Your clinic is not active.")

    return build_settings(clinic)


def update_my_settings(
    db: Session,
    current_user: User,
    data: BookingPaymentSettingsUpdate,
):
    try:
        administrator = get_admin_record(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == administrator.clinic_id,
                Clinic.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(
                403,
                "Your clinic is not active.",
            )

        if clinic.booking_payment_version != data.expected_version:
            raise HTTPException(
                409,
                "Booking payment settings changed. "
                "Reload them before saving again.",
            )

        if clinic.booking_deposit_amount != data.deposit_amount:
            clinic.booking_deposit_amount = data.deposit_amount
            clinic.booking_payment_version += 1

        result = build_settings(clinic)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise