from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Clinic, ClinicAdministrator, User, Veterinarian
from app.schemas.clinic import ClinicUpdate
from app.services.admin_profile_service import get_admin_record


def get_my_clinic(db: Session, current_user: User) -> Clinic:
    administrator = get_admin_record(db, current_user)

    return administrator.clinic


def update_my_clinic(
    db: Session,
    current_user: User,
    data: ClinicUpdate,
) -> Clinic:
    administrator = get_admin_record(db, current_user)
    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update.",
        )

    try:
        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == administrator.clinic_id,
                Clinic.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(
                status_code=403,
                detail="Your clinic is not active.",
            )

        latitude = changes.get("latitude", clinic.latitude)
        longitude = changes.get("longitude", clinic.longitude)

        if (latitude is None) != (longitude is None):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Latitude and longitude must both be provided "
                    "or both be cleared."
                ),
            )

        for field, value in changes.items():
            setattr(clinic, field, value)

        if "clinic_name" in changes:
            # Keep legacy name columns consistent during migration.
            for model in (ClinicAdministrator, Veterinarian):
                db.execute(
                    update(model)
                    .where(model.clinic_id == clinic.clinic_id)
                    .values(clinic_name=clinic.clinic_name)
                )

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(clinic)
    return clinic