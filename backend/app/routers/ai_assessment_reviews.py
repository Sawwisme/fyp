from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.ai_assessment_reviews import (
    AIAssessmentReviewRequest,
    AIAssessmentReviewSubmit,
)
from app.services import ai_assessment_review_service as service


router = APIRouter(
    prefix="/ai-assessment-reviews",
    tags=["AI Assessment Reviews"],
)


@router.post("/assessments/{analysis_id}")
def request_review(
    data: AIAssessmentReviewRequest,
    analysis_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
):
    raise HTTPException(
        status_code=410,
        detail=(
            "Please book a dental examination from your AI "
            "assessment result page to discuss the findings with a vet."
        ),
    )


@router.get("")
def list_reviews(
    status: Literal[
        "pending", "reviewed", "cancelled"
    ] | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("pet_owner", "veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return service.list_reviews(
        db,
        current_user,
        status,
        offset,
        limit,
    )


@router.get("/{review_id}")
def get_review(
    review_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner", "veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return service.get_review(
        db,
        current_user,
        review_id,
    )


@router.post("/{review_id}/decision")
def submit_review(
    data: AIAssessmentReviewSubmit,
    review_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return service.submit_review(
        db,
        current_user,
        review_id,
        data,
    )


@router.get("/{review_id}/media/{kind}")
def get_review_media(
    kind: Literal[
        "original", "heatmap", "segmentation", "summary"
    ],
    review_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner", "veterinarian")
    ),
    db: Session = Depends(get_db),
):
    target = service.get_review_media_path(
        db,
        current_user,
        review_id,
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