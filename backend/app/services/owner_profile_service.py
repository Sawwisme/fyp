from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.owner_profile import OwnerProfileUpdate
from app.services.pet_service import get_owner_profile


def get_profile(db: Session, current_user: User) -> dict:
    owner = get_owner_profile(db, current_user)

    return {
        "pet_owner_id": owner.pet_owner_id,
        "default_address": owner.default_address,
        "user": current_user,
    }


def update_profile(
    db: Session,
    current_user: User,
    data: OwnerProfileUpdate,
) -> dict:
    owner = get_owner_profile(db, current_user)
    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one field to update.",
        )

    for field, value in changes.items():
        if field == "default_address":
            owner.default_address = value
        else:
            setattr(current_user, field, value)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(current_user)
    db.refresh(owner)

    return {
        "pet_owner_id": owner.pet_owner_id,
        "default_address": owner.default_address,
        "user": current_user,
    }