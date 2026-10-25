from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.consultations import (
    ConsultationResponse,
    ConsultationSave,
)
from app.services import consultation_service


router = APIRouter(
    prefix="/consultations",
    tags=["Consultations"],
)


@router.post(
    "/appointments/{appointment_id}/start",
    response_model=ConsultationResponse,
)
def start_consultation(
    appointment_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return consultation_service.start_consultation(
        db, current_user, appointment_id
    )


@router.get(
    "/{consultation_id}",
    response_model=ConsultationResponse,
)
def get_consultation(
    consultation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return consultation_service.get_consultation(
        db, current_user, consultation_id
    )


@router.put(
    "/{consultation_id}",
    response_model=ConsultationResponse,
)
def save_consultation(
    data: ConsultationSave,
    consultation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return consultation_service.save_consultation(
        db, current_user, consultation_id, data
    )