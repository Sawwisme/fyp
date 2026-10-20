from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    Clinic,
    ClinicAdministrator,
    User,
    Veterinarian,
)
from app.schemas.admin_profile import AdminProfileUpdate


def get_admin_record(
    db: Session,
    current_user: User,
) -> ClinicAdministrator:
    if (
        current_user.role != "clinic_administrator"
        or current_user.status != "active"
    ):
        raise HTTPException(
            status_code=403,
            detail="An active administrator account is required.",
        )

    administrator = db.scalar(
        select(ClinicAdministrator)
        .join(ClinicAdministrator.clinic)
        .where(
            ClinicAdministrator.user_id == current_user.user_id,
            ClinicAdministrator.membership_status == "approved",
            Clinic.status == "active",
        )
    )

    if administrator is None:
        raise HTTPException(
            status_code=403,
            detail="Approved membership of an active clinic is required.",
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
        "clinic_id": administrator.clinic_id,
        "clinic_name": administrator.clinic.clinic_name,
        "membership_status": administrator.membership_status,
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
            status_code=400,
            detail="Provide at least one field to update.",
        )

    try:
        if "full_name" in changes:
            current_user.full_name = changes["full_name"]

        if "phone_number" in changes:
            current_user.phone_number = changes["phone_number"]

        if "clinic_name" in changes:
            new_name = changes["clinic_name"]
            administrator.clinic.clinic_name = new_name

            # Keep the old name columns consistent during migration.
            db.execute(
                update(ClinicAdministrator)
                .where(
                    ClinicAdministrator.clinic_id
                    == administrator.clinic_id
                )
                .values(clinic_name=new_name)
            )

            db.execute(
                update(Veterinarian)
                .where(
                    Veterinarian.clinic_id == administrator.clinic_id
                )
                .values(clinic_name=new_name)
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(current_user)
    db.refresh(administrator)

    return build_profile(administrator, current_user)