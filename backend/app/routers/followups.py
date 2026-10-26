from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.followups import (
    FollowupResponse,
    FollowupReview,
    FollowupCancel,
    FollowupActionResponse,
)
from app.services import followup_service


router = APIRouter(
    prefix="/followups",
    tags=["Follow-up Care"],
)


@router.get("", response_model=list[FollowupResponse])
def list_my_followups(
    search: str | None = Query(default=None, max_length=100),
    status: Literal[
        "pending", "completed", "cancelled"
    ] | None = "pending",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return followup_service.list_my_followups(
        db,
        current_user,
        search,
        status,
        offset,
        limit,
    )

@router.post(
    "/{followup_id}/review",
    response_model=FollowupActionResponse,
)
def record_review(
    data: FollowupReview,
    followup_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return followup_service.record_review(
        db, current_user, followup_id, data
    )


@router.post(
    "/{followup_id}/cancel",
    response_model=FollowupActionResponse,
)
def cancel_followup(
    data: FollowupCancel,
    followup_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return followup_service.cancel_followup(
        db, current_user, followup_id, data
    )