import hashlib

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Clinic, ClinicAdministrator, User
from app.schemas.admin_registration import AdminRegistrationRequest
from app.services.auth_service import hash_password
from app.services.clinic_discovery_service import verify_selection


def list_registration_clinics(
    db: Session,
    offset: int,
    limit: int,
):
    return list(
        db.scalars(
            select(Clinic)
            .where(Clinic.status == "active")
            .order_by(Clinic.clinic_name, Clinic.clinic_id)
            .offset(offset)
            .limit(limit)
        ).all()
    )


def register_administrator(
    db: Session,
    data: AdminRegistrationRequest,
) -> None:
    try:
        email = str(data.email).strip().lower()

        existing_user = db.scalar(
            select(User.user_id).where(
                func.lower(User.email) == email
            )
        )

        if existing_user is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This email is already registered. "
                    "Use a different email for this account."
                ),
            )

        # Public registration cannot join an existing clinic.
        if data.clinic_id is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This clinic is already registered. "
                    "Contact your clinic administrator."
                ),
            )

        if data.manual_clinic is not None:
            details = data.manual_clinic

            identity = (
                f"{details.clinic_name.casefold()}\n"
                f"{details.address.casefold()}"
            )

            fingerprint = hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()[:32]

            values = {
                "clinic_code": f"MANUAL-{fingerprint}",
                "clinic_name": details.clinic_name,
                "address": details.address,
            }

        else:
            selected = verify_selection(
                data.selection_token.get_secret_value()
            )

            values = {
                "clinic_code": (
                    f"OSM-{selected.osm_type.upper()}-{selected.osm_id}"
                ),
                "clinic_name": selected.clinic_name,
                "address": selected.address,
                "latitude": selected.latitude,
                "longitude": selected.longitude,
                "osm_type": selected.osm_type,
                "osm_id": selected.osm_id,
            }

        conditions = [
            Clinic.clinic_code == values["clinic_code"]
        ]

        if values.get("osm_id") is not None:
            conditions.append(
                (Clinic.osm_type == values["osm_type"])
                & (Clinic.osm_id == values["osm_id"])
            )

        # Also catch matching manual/map submissions where
        # both the clinic name and address are the same.
        if values.get("address"):
            conditions.append(
                (
                    func.lower(func.trim(Clinic.clinic_name))
                    == values["clinic_name"].strip().lower()
                )
                & (
                    func.lower(func.trim(Clinic.address))
                    == values["address"].strip().lower()
                )
            )

        existing_clinic = db.scalar(
            select(Clinic.clinic_id)
            .where(or_(*conditions))
            .with_for_update()
        )

        if existing_clinic is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This clinic is already registered. "
                    "Contact your clinic administrator."
                ),
            )

        clinic = Clinic(
            **values,
            status="active",
        )

        db.add(clinic)
        db.flush()

        user = User(
            full_name=data.full_name,
            email=email,
            phone_number=data.phone_number,
            password_hash=hash_password(
                data.password.get_secret_value()
            ),
            role="clinic_administrator",
            status="active",
        )

        user.clinic_administrator = ClinicAdministrator(
            clinic_id=clinic.clinic_id,
            clinic_name=clinic.clinic_name,
            membership_status="approved",
        )

        db.add(user)
        db.commit()

    except IntegrityError as error:
        db.rollback()

        error_code = getattr(error.orig, "args", (None,))[0]

        if error_code == 1062:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This email or clinic is already registered. "
                    "Use your existing account or contact "
                    "your clinic administrator."
                ),
            ) from None

        raise HTTPException(
            status_code=500,
            detail="Unable to register your clinic.",
        ) from None

    except Exception:
        db.rollback()
        raise