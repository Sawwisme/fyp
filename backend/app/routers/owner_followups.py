from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Path,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.services import followup_submission_service
from app.schemas.followup_submissions import (
    FollowupSubmissionResponse,
    OwnerFollowupSubmissionState,
    OwnerFollowupListItem,
)


router = APIRouter(
    prefix="/owner-followups",
    tags=["Owner Follow-up Care"],
)


@router.post(
    "/{followup_id}/submissions",
    response_model=FollowupSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(
    followup_id: int = Path(ge=1, le=2147483647),
    owner_comment: str | None = Form(
        default=None,
        max_length=5000,
    ),
    files: list[UploadFile] = File(default=[]),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return followup_submission_service.create_submission(
        db,
        current_user,
        followup_id,
        owner_comment,
        files,
    )


@router.get(
    "/{followup_id}/submissions",
    response_model=list[FollowupSubmissionResponse],
)
def list_submissions(
    followup_id: int = Path(ge=1, le=2147483647),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return followup_submission_service.list_owner_submissions(
        db,
        current_user,
        followup_id,
        offset,
        limit,
    )

@router.get(
    "/{followup_id}/submission-state",
    response_model=OwnerFollowupSubmissionState,
)
def get_submission_state(
    followup_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return followup_submission_service.get_owner_submission_state(
        db,
        current_user,
        followup_id,
    )

@router.get(
    "",
    response_model=list[OwnerFollowupListItem],
)
def list_followups(
    task_status: Literal[
        "pending", "completed", "cancelled"
    ] | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return followup_submission_service.list_owner_followups(
        db,
        current_user,
        task_status,
        offset,
        limit,
    )