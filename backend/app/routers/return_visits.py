from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from datetime import date
from typing import Literal

from fastapi import Query
from app.schemas.availability import AvailableSlotResponse
from app.schemas.clinic_appointments import ReturnVisitContext
from app.services import availability_service, return_visit_service
from app.services.vet_profile_service import get_profile

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.clinic_appointments import (
    ClinicAppointmentResponse,
    ReturnVisitCreate,
)
from app.services import clinic_appointment_service


router = APIRouter(
    prefix="/return-visits",
    tags=["Return Visits"],
)


@router.post(
    "",
    response_model=ClinicAppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_return_visit(
    data: ReturnVisitCreate,
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return clinic_appointment_service.create_appointment(
        db,
        current_user,
        data,
    )

@router.get(
    "/context",
    response_model=ReturnVisitContext,
)
def get_booking_context(
    source_type: Literal["treatment", "followup"],
    source_id: int = Query(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return return_visit_service.get_booking_context(
        db,
        current_user,
        source_type,
        source_id,
    )


@router.get(
    "/slots",
    response_model=list[AvailableSlotResponse],
)
def get_return_visit_slots(
    appointment_date: date,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    veterinarian = get_profile(db, current_user)

    return availability_service.list_available_slots(
        db,
        veterinarian.veterinarian_id,
        appointment_date,
        offset,
        limit,
    )