from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.clinic_appointments import (
    ClinicAppointmentCreate,
    ClinicAppointmentResponse,
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