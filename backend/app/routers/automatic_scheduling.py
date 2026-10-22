from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.automatic_scheduling import (
    AutomaticSchedulingResponse,
    AutomaticSchedulingUpdate,
)
from app.services import automatic_scheduling_service


router = APIRouter(
    prefix="/automatic-scheduling",
    tags=["Automatic Scheduling"],
)


@router.get(
    "",
    response_model=list[AutomaticSchedulingResponse],
)
def read_settings(
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return automatic_scheduling_service.read_rules(
        db,
        current_user,
    )


@router.put(
    "",
    response_model=list[AutomaticSchedulingResponse],
)
def save_settings(
    data: AutomaticSchedulingUpdate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return automatic_scheduling_service.save_rules(
        db,
        current_user,
        data,
    )