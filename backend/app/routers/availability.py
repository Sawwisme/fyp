from datetime import date

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.availability import (
    AvailableSlotResponse,
    VeterinarianSummary,
    ClinicSummary,
)
from app.services import availability_service


router = APIRouter(
    prefix="/availability",
    tags=["Appointment Availability"],
)


@router.get(
    "/veterinarians",
    response_model=list[VeterinarianSummary],
)
def get_veterinarians(
    clinic_id: int | None = Query(
        default=None, ge=1, le=2147483647
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return availability_service.list_veterinarians(
        db,
        offset,
        limit,
        clinic_id,
    )

@router.get(
    "/veterinarians/{veterinarian_id}/slots",
    response_model=list[AvailableSlotResponse],
    responses={
        400: {"description": "Date is in the past"},
        404: {"description": "Veterinarian unavailable"},
    },
)
def get_available_slots(
    appointment_date: date,
    veterinarian_id: int = Path(gt=0, le=2147483647),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return availability_service.list_available_slots(
        db,
        veterinarian_id,
        appointment_date,
        offset,
        limit,
    )

@router.get(
    "/clinics",
    response_model=list[ClinicSummary],
)
def get_clinics(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return availability_service.list_clinics(
        db,
        offset,
        limit,
    )