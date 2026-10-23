from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.clinic_appointments import (
    ClinicAppointmentCreate,
    ClinicAppointmentResponse,
    ClinicAppointmentReschedule,
)
from app.services import clinic_appointment_service


router = APIRouter(
    prefix="/clinic-appointments",
    tags=["Clinic Appointments"],
)


@router.post(
    "",
    response_model=ClinicAppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_appointment(
    data: ClinicAppointmentCreate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_appointment_service.create_appointment(
        db,
        current_user,
        data,
    )

@router.post("/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_appointment_service.cancel_appointment(
        db,
        current_user,
        appointment_id,
    )

@router.post("/{appointment_id}/reschedule")
def reschedule_appointment(
    data: ClinicAppointmentReschedule,
    appointment_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_appointment_service.reschedule_appointment(
        db,
        current_user,
        appointment_id,
        data.time_slot_id,
    )