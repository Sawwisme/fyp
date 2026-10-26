from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.treatment_progress import (
    TreatmentProgressResponse,
    TreatmentProgressUpdate,
    CompletionConsultationOption,
)
from app.services import treatment_progress_service


router = APIRouter(
    prefix="/treatment-plans",
    tags=["Treatment Plans"],
)


@router.patch(
    "/{treatment_id}/progress",
    response_model=TreatmentProgressResponse,
)
def update_progress(
    data: TreatmentProgressUpdate,
    treatment_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return treatment_progress_service.update_progress(
        db,
        current_user,
        treatment_id,
        data,
    )

@router.get(
    "/{treatment_id}/completion-consultations",
    response_model=list[CompletionConsultationOption],
)
def list_completion_consultations(
    treatment_id: int = Path(ge=1, le=2147483647),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return treatment_progress_service.list_completion_consultations(
        db,
        current_user,
        treatment_id,
        offset,
        limit,
    )