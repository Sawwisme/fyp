from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.schedule import ScheduleCreate, ScheduleResponse
from app.services import schedule_service


router = APIRouter(
    prefix="/schedules",
    tags=["Schedule Management"],
)


@router.post(
    "",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Schedule does not start in the future"},
        404: {"description": "Eligible veterinarian not found"},
        409: {"description": "Overlapping schedule"},
    },
)
def create_schedule(
    data: ScheduleCreate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return schedule_service.create_schedule(
        db,
        current_user,
        data,
    )


@router.get(
    "",
    response_model=list[ScheduleResponse],
)
def list_schedules(
    veterinarian_id: int | None = Query(
        default=None,
        ge=1,
        le=2147483647,
    ),
    schedule_date: date | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return schedule_service.list_schedules(
        db,
        current_user,
        veterinarian_id,
        schedule_date,
        offset,
        limit,
    )