from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.clinic_appointments import (
    ClinicAppointmentCreate,
    ClinicAppointmentResponse,
    ClinicAppointmentReschedule,
)
from app.services import clinic_appointment_service, vet_absence_service
from app.schemas.vet_absences import RearrangementResolve

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

@router.get("/rearrangements")
def list_rearrangements(
    pending_only: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return vet_absence_service.list_clinic_rearrangements(
        db,
        current_user,
        pending_only,
        offset,
        limit,
    )

@router.post("/rearrangements/{affected_id}/resolve")
def resolve_rearrangement(
    data: RearrangementResolve,
    affected_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return vet_absence_service.resolve_rearrangement(
        db,
        current_user,
        affected_id,
        data,
    )