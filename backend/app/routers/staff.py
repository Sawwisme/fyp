from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.staff import (
    VeterinarianCreate,
    VeterinarianResponse,
    AdministratorCreate,
    AdministratorResponse,
)
from app.services import staff_service


router = APIRouter(
    prefix="/staff",
    tags=["Staff Management"],
)


@router.post(
    "/veterinarians",
    response_model=VeterinarianResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "Email or registration number already exists"},
    },
)
def create_veterinarian(
    data: VeterinarianCreate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return staff_service.create_veterinarian(
        db,
        current_user,
        data,
    )


@router.get(
    "/veterinarians",
    response_model=list[VeterinarianResponse],
)
def list_veterinarians(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return staff_service.list_veterinarians(
        db,
        current_user,
        offset,
        limit,
    )

@router.post(
    "/administrators",
    response_model=AdministratorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_administrator(
    data: AdministratorCreate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return staff_service.create_administrator(
        db,
        current_user,
        data,
    )

@router.get(
    "/administrators",
    response_model=list[AdministratorResponse],
)
def list_administrators(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return staff_service.list_administrators(
        db,
        current_user,
        offset,
        limit,
    )