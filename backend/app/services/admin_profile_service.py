from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ClinicAdministrator, User
from app.schemas.admin_profile import AdminProfileUpdate


def get_admin_record(
    db: Session,
    current_user: User,
) -> ClinicAdministrator:
    administrator = db.scalar(
        select(ClinicAdministrator).where(
            ClinicAdministrator.user_id == current_user.user_id
        )
    )

    if administrator is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has no administrator profile.",
        )

    return administrator


def build_profile(
    administrator: ClinicAdministrator,
    current_user: User,
) -> dict:
    return {
        "clinic_administrator_id": (
            administrator.clinic_administrator_id
        ),
        "clinic_name": administrator.clinic_name,
        "user": current_user,
    }


def get_profile(db: Session, current_user: User) -> dict:
    administrator = get_admin_record(db, current_user)

    return build_profile(administrator, current_user)


def update_profile(
    db: Session,
    current_user: User,
    data: AdminProfileUpdate,
) -> dict:
    administrator = get_admin_record(db, current_user)
    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one field to update.",
        )

    if "full_name" in changes:
        current_user.full_name = changes["full_name"]

    if "phone_number" in changes:
        current_user.phone_number = changes["phone_number"]

    if "clinic_name" in changes:
        administrator.clinic_name = changes["clinic_name"]

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(current_user)
    db.refresh(administrator)

    return build_profile(administrator, current_user)