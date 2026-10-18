from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.vet_profile import (
    VetProfileResponse,
    VetProfileUpdate,
)
from app.services import vet_profile_service


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