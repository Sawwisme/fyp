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
        "default_state": owner.default_state,
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

    # An address change must not silently retain an old destination state.
    if (
        "default_address" in changes
        and changes["default_address"] != owner.default_address
        and "default_state" not in changes
    ):
        owner.default_state = None

    for field, value in changes.items():
        if field in {"default_address", "default_state"}:
            setattr(owner, field, value)
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
        "default_state": owner.default_state,
    }