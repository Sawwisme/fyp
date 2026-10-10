from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.owner_profile import (
    OwnerProfileResponse,
    OwnerProfileUpdate,
)
from app.services import owner_profile_service


router = APIRouter(
    prefix="/owners",
    tags=["Owner Profile"],
)


@router.get("/me", response_model=OwnerProfileResponse)
def get_my_profile(
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return owner_profile_service.get_profile(db, current_user)


@router.patch(
    "/me",
    response_model=OwnerProfileResponse,
    responses={
        400: {"description": "No fields supplied"},
    },
)
def edit_my_profile(
    data: OwnerProfileUpdate,
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return owner_profile_service.update_profile(
        db,
        current_user,
        data,
    )