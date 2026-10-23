from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.owner_appointments import (
    OwnerAppointmentCreate,
    OwnerAppointmentResponse,
)
from app.services import owner_appointment_service


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