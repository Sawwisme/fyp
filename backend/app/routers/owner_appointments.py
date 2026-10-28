from datetime import date

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.owner_appointments import (
    OwnerAppointmentCreate,
    OwnerAppointmentResponse,
    OwnerAppointmentListItem,
    OwnerAppointmentReschedule,
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

@router.get(
    "",
    response_model=list[OwnerAppointmentListItem],
)
def get_my_appointments(
    appointment_date: date | None = None,
    followup_only: bool = Query(default=False),
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
        followup_only=followup_only,
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