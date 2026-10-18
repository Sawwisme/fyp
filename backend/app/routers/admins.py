from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.admin_profile import (
    AdminProfileResponse,
    AdminProfileUpdate,
)
from app.services import admin_profile_service


router = APIRouter(
    prefix="/admins",
    tags=["Administrator Profile"],
)


@router.get(
    "/me",
    response_model=AdminProfileResponse,
)
def get_my_profile(
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return admin_profile_service.get_profile(db, current_user)


@router.patch(
    "/me",
    response_model=AdminProfileResponse,
    responses={
        400: {"description": "No fields supplied"},
    },
)
def edit_my_profile(
    data: AdminProfileUpdate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return admin_profile_service.update_profile(
        db,
        current_user,
        data,
    )