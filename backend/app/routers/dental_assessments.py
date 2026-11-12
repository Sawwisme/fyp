from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from typing import Literal

from fastapi.responses import FileResponse

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.services import dental_assessment_service


router = APIRouter(
    prefix="/dental-assessments",
    tags=["Dental Assessments"],
)


@router.post("/images/{image_id}", status_code=202)
def start_assessment(
    image_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return dental_assessment_service.queue_assessment(
        db,
        current_user,
        image_id,
    )

@router.get("/history")
def list_history(
    pet_id: int = Query(ge=1, le=2147483647),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return dental_assessment_service.list_assessment_history(
        db,
        current_user,
        pet_id,
        offset=offset,
        limit=limit,
    )

@router.get("/{job_id}")
def get_assessment(
    job_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return dental_assessment_service.get_assessment(
        db,
        current_user,
        job_id,
    )

@router.get("/{job_id}/media/{kind}")
def get_result_image(
    kind: Literal["heatmap", "segmentation", "summary"],
    job_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    target = dental_assessment_service.get_result_image_path(
        db,
        current_user,
        job_id,
        kind,
    )

    return FileResponse(
        path=target,
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )