from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session
from typing import Literal
from fastapi.responses import FileResponse
from datetime import date

from fastapi import Query

from app.schemas.schedule import ScheduleResponse
from app.schemas.vet_appointments import (
    VetAppointmentResponse,
    VetCalendarEntry,
)
from app.services import vet_appointment_service, vet_scan_service, shared_medical_history_service

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.vet_profile import (
    VetProfileResponse,
    VetProfileUpdate,
)
from app.services import vet_profile_service, vet_absence_service

from app.schemas.vet_absences import (
    VetAbsenceCreate,
    VetAbsenceCreated,
    VetAbsenceResponse,
)


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
    appointment_date: date | None = None,
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

@router.get(
    "/me/appointments/summary",
    response_model=dict[str, int],
)
def get_my_appointment_summary(
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return vet_appointment_service.get_my_all_time_count(
        db,
        current_user,
    )

@router.post(
    "/me/absences",
    response_model=VetAbsenceCreated,
    status_code=201,
)
def report_my_absence(
    data: VetAbsenceCreate,
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return vet_absence_service.create_absence(
        db,
        current_user,
        data,
    )

@router.get(
    "/me/absences",
    response_model=list[VetAbsenceResponse],
)
def list_my_absences(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return vet_absence_service.list_my_absences(
        db,
        current_user,
        offset,
        limit,
    )

@router.get(
    "/me/absence-periods",
    response_model=list[VetAbsenceResponse],
)
def get_my_absence_periods(
    start_date: date,
    end_date: date,
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return vet_absence_service.list_my_absence_periods(
        db,
        current_user,
        start_date,
        end_date,
    )

@router.post("/me/absences/{absence_id}/withdraw")
def withdraw_my_absence(
    absence_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return vet_absence_service.withdraw_my_absence(
        db,
        current_user,
        absence_id,
    )

@router.get("/me/appointments/{appointment_id}/ai-assessment")
def get_appointment_ai_assessment(
    appointment_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return vet_scan_service.get_linked_scan(
        db,
        current_user,
        appointment_id,
    )

@router.get(
    "/me/appointments/{appointment_id}/ai-assessment/media/{kind}"
)
def get_appointment_ai_assessment_media(
    kind: Literal["original", "heatmap", "segmentation", "summary"],
    appointment_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    target = vet_scan_service.get_linked_scan_media(
        db,
        current_user,
        appointment_id,
        kind,
    )

    return FileResponse(
        path=target,
        media_type=(
            "image/jpeg" if kind == "original" else "image/png"
        ),
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

@router.get(
    "/me/appointment-assessments",
    response_model=list[VetAppointmentResponse],
)
def list_my_appointment_assessments(
    appointment_date: date | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return vet_appointment_service.list_my_appointments(
        db,
        current_user,
        appointment_date,
        offset,
        limit,
        linked_scans_only=True,
    )

@router.get("/me/appointments/{appointment_id}/shared-history")
def get_shared_appointment_history(
    appointment_id: int = Path(ge=1, le=2147483647),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return shared_medical_history_service.list_shared_history(
        db,
        current_user,
        appointment_id,
        offset=offset,
        limit=limit,
    )