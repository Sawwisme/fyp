from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.pet import PetCreate, PetResponse, PetUpdate
from app.services import pet_service


router = APIRouter(
    prefix="/pets",
    tags=["Pets"],
)


@router.post(
    "",
    response_model=PetResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_pet(
    data: PetCreate,
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return pet_service.create_pet(db, current_user, data)


@router.get("", response_model=list[PetResponse])
def get_my_pets(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return pet_service.list_pets(db, current_user, offset, limit)


@router.get(
    "/{pet_id}",
    response_model=PetResponse,
    responses={
        404: {"description": "Pet not found or belongs to another owner"},
    },
)
def get_my_pet(
    pet_id: int = Path(gt=0, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return pet_service.get_pet(db, current_user, pet_id)

@router.patch(
    "/{pet_id}",
    response_model=PetResponse,
    responses={
        400: {"description": "No fields supplied"},
        404: {"description": "Pet not found or belongs to another owner"},
    },
)
def edit_my_pet(
    data: PetUpdate,
    pet_id: int = Path(gt=0, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return pet_service.update_pet(db, current_user, pet_id, data)