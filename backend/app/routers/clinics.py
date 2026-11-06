from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.clinic import ClinicResponse, ClinicUpdate
from app.schemas.clinic_hours import WorkingHoursUpdate, WorkingPeriod
from app.services import clinic_hours_service, clinic_booking_payment_service, clinic_service
from app.schemas.clinic_booking_payment import (
    BookingPaymentSettingsResponse,
    BookingPaymentSettingsUpdate,
)


router = APIRouter(
    prefix="/clinics",
    tags=["Clinic Settings"],
)


@router.get("/me", response_model=ClinicResponse)
def get_my_clinic(
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_service.get_my_clinic(db, current_user)


@router.patch("/me", response_model=ClinicResponse)
def update_my_clinic(
    data: ClinicUpdate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_service.update_my_clinic(
        db,
        current_user,
        data,
    )

@router.get(
    "/me/working-hours",
    response_model=list[WorkingPeriod],
)
def get_my_working_hours(
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_hours_service.get_my_hours(db, current_user)


@router.put(
    "/me/working-hours",
    response_model=list[WorkingPeriod],
)
def replace_my_working_hours(
    data: WorkingHoursUpdate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_hours_service.replace_my_hours(
        db,
        current_user,
        data,
    )

@router.get(
    "/me/booking-payment-settings",
    response_model=BookingPaymentSettingsResponse,
)
def get_my_booking_payment_settings(
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_booking_payment_service.get_my_settings(
        db,
        current_user,
    )


@router.put(
    "/me/booking-payment-settings",
    response_model=BookingPaymentSettingsResponse,
)
def update_my_booking_payment_settings(
    data: BookingPaymentSettingsUpdate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_booking_payment_service.update_my_settings(
        db,
        current_user,
        data,
    )