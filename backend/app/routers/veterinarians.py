from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from datetime import date

from fastapi import Query

from app.schemas.schedule import ScheduleResponse
from app.schemas.vet_appointments import (
    VetAppointmentResponse,
    VetCalendarEntry,
)
from app.services import vet_appointment_service

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.vet_profile import (
    VetProfileResponse,
    VetProfileUpdate,
)
from app.services import vet_profile_service


router = APIRouter(
    prefix="/veterinarians",
    tags=["Veterinarian Profile"],
)


@router.get(
    "/me",
    response_model=VetProfileResponse,
)
def get_my_profile(
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return vet_profile_service.get_profile(db, current_user)


@router.patch(
    "/me",
    response_model=VetProfileResponse,
    responses={
        400: {"description": "No fields supplied"},
    },
)
def edit_my_profile(
    data: VetProfileUpdate,
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return vet_profile_service.update_profile(
        db,
        current_user,
        data,
    )

@router.get(
    "/me/schedules",
    response_model=list[ScheduleResponse],
)
def get_my_schedules(
    schedule_date: date,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return vet_profile_service.list_my_schedules(
        db,
        current_user,
        schedule_date,
        offset,
        limit,
    )

@router.get(
    "/me/appointments",
    response_model=list[VetAppointmentResponse],
)
def get_my_appointments(
    appointment_date: date,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return vet_appointment_service.list_my_appointments(
        db,
        current_user,
        appointment_date,
        offset,
        limit,
    )

@router.get(
    "/me/calendar",
    response_model=list[VetCalendarEntry],
)
def get_my_calendar(
    start_date: date,
    end_date: date,
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return vet_appointment_service.get_my_calendar(
        db,
        current_user,
        start_date,
        end_date,
    )