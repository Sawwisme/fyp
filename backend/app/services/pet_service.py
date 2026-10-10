from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Pet, PetOwner, User
from app.schemas.pet import PetCreate, PetUpdate


def get_owner_profile(db: Session, current_user: User) -> PetOwner:
    owner = db.scalar(
        select(PetOwner).where(
            PetOwner.user_id == current_user.user_id
        )
    )

    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A pet owner profile is required.",
        )

    return owner


def create_pet(
    db: Session,
    current_user: User,
    data: PetCreate,
) -> Pet:
    owner = get_owner_profile(db, current_user)

    pet = Pet(
        pet_owner_id=owner.pet_owner_id,
        **data.model_dump(),
    )

    try:
        db.add(pet)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(pet)
    return pet


def list_pets(
    db: Session,
    current_user: User,
    offset: int,
    limit: int,
) -> list[Pet]:
    owner = get_owner_profile(db, current_user)

    query = (
        select(Pet)
        .where(Pet.pet_owner_id == owner.pet_owner_id)
        .order_by(Pet.pet_id)
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(query).all())


def get_pet(
    db: Session,
    current_user: User,
    pet_id: int,
) -> Pet:
    owner = get_owner_profile(db, current_user)

    pet = db.scalar(
        select(Pet).where(
            Pet.pet_id == pet_id,
            Pet.pet_owner_id == owner.pet_owner_id,
        )
    )

    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pet not found.",
        )

    return pet

def update_pet(
    db: Session,
    current_user: User,
    pet_id: int,
    data: PetUpdate,
) -> Pet:
    pet = get_pet(db, current_user, pet_id)
    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one field to update.",
        )

    for field, value in changes.items():
        setattr(pet, field, value)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(pet)
    return pet