from datetime import date

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.owner_appointments import (
    OwnerAppointmentCreate,
    OwnerAppointmentResponse,
    OwnerAppointmentListItem,
    OwnerAppointmentReschedule,
    OwnerBookingCheckoutResponse,
    OwnerBookingRefundResponse,
)
from app.services import owner_appointment_service
from app.schemas.clinic_booking_payment import (
    BookingPaymentSettingsResponse,
)

from app.services.booking_deposit_service import get_booking_quote

from app.services.booking_checkout_service import (
    open_booking_checkout,
)

from app.services.owner_booking_refund_service import (
    get_my_booking_refund,
)

router = APIRouter(
    prefix="/owner-appointments",
    tags=["Owner Appointments"],
)


@router.post(
    "",
    response_model=OwnerAppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_appointment(
    data: OwnerAppointmentCreate,
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return owner_appointment_service.create_appointment(
        db,
        current_user,
        data,
    )

@router.get(
    "",
    response_model=list[OwnerAppointmentListItem],
)
def get_my_appointments(
    appointment_date: date | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return owner_appointment_service.list_my_appointments(
        db,
        current_user,
        appointment_date,
        offset,
        limit,
    )

@router.post("/{appointment_id}/cancel")
def cancel_my_appointment(
    appointment_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return owner_appointment_service.cancel_my_appointment(
        db,
        current_user,
        appointment_id,
    )

@router.post(
    "/{appointment_id}/reschedule",
    response_model=OwnerAppointmentResponse,
)
def reschedule_my_appointment(
    data: OwnerAppointmentReschedule,
    appointment_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return owner_appointment_service.reschedule_my_appointment(
        db,
        current_user,
        appointment_id,
        data.time_slot_id,
    )

@router.get(
    "/clinics/{clinic_id}/payment-quote",
    response_model=BookingPaymentSettingsResponse,
)
def get_clinic_booking_payment_quote(
    clinic_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return get_booking_quote(
        db,
        current_user,
        clinic_id,
    )


@router.get(
    "/stripe/return",
    response_class=HTMLResponse,
)
def booking_payment_return():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1">
        <title>VetDental appointment payment</title>
        <style>
            body {
                margin: 0;
                padding: 48px 24px;
                background: #f5f7f5;
                color: #23352a;
                font: 16px/1.6 Arial, sans-serif;
            }
            main {
                max-width: 480px;
                margin: auto;
                padding: 28px;
                background: white;
                border-radius: 16px;
            }
            h1 { color: #176b32; font-size: 24px; }
        </style>
    </head>
    <body>
        <main>
            <h1>Return to VetDental</h1>
            <p>
                Open the app and refresh your appointment
                to check its payment and booking status.
            </p>
            <p>
                Your appointment is confirmed only after
                payment has been verified.
            </p>
        </main>
    </body>
    </html>
    """

@router.post(
    "/{appointment_id}/checkout",
    response_model=OwnerBookingCheckoutResponse,
)
def open_my_booking_checkout(
    appointment_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return open_booking_checkout(
        db,
        current_user,
        appointment_id,
    )

@router.get(
    "/{appointment_id}/deposit-refund",
    response_model=OwnerBookingRefundResponse | None,
)
def get_my_deposit_refund(
    appointment_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return get_my_booking_refund(
        db,
        current_user,
        appointment_id,
    )