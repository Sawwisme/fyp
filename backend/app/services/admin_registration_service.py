from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import hashlib

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


def resolve_registration_clinic(
    db: Session,
    data: AdminRegistrationRequest,
) -> Clinic:
    if data.clinic_id is not None:
        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == data.clinic_id,
                Clinic.status == "active",
            )
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(
                status_code=400,
                detail="Select an available clinic.",
            )

        return clinic

    if data.manual_clinic is not None:
        return resolve_manual_clinic(db, data.manual_clinic)

    selected = verify_selection(
        data.selection_token.get_secret_value()
    )

    query = select(Clinic).where(
        Clinic.osm_type == selected.osm_type,
        Clinic.osm_id == selected.osm_id,
    )

    clinic = db.scalar(query.with_for_update())

    if clinic is None:
        clinic = Clinic(
            clinic_code=(
                f"OSM-{selected.osm_type.upper()}-{selected.osm_id}"
            ),
            clinic_name=selected.clinic_name,
            address=selected.address,
            latitude=selected.latitude,
            longitude=selected.longitude,
            osm_type=selected.osm_type,
            osm_id=selected.osm_id,
            status="pending",
        )

        try:
            # Preserve the outer transaction if another registration
            # creates the same map clinic concurrently.
            with db.begin_nested():
                db.add(clinic)
                db.flush()
        except IntegrityError:
            clinic = db.scalar(
                query.execution_options(
                    populate_existing=True
                ).with_for_update()
            )

            if clinic is None:
                raise

    if clinic.status not in {"active", "pending"}:
        raise HTTPException(
            status_code=400,
            detail="This clinic is not accepting registrations.",
        )

    return clinic


def register_administrator(
    db: Session,
    data: AdminRegistrationRequest,
) -> None:
    try:
        existing_user = db.scalar(
            select(User.user_id).where(
                User.email == str(data.email)
            )
        )

        if existing_user is not None:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists.",
            )

        clinic = resolve_registration_clinic(db, data)

        user = User(
            full_name=data.full_name,
            email=str(data.email),
            phone_number=data.phone_number,
            password_hash=hash_password(
                data.password.get_secret_value()
            ),
            role="clinic_administrator",
            status="pending",
        )

        user.clinic_administrator = ClinicAdministrator(
            clinic_id=clinic.clinic_id,
            clinic_name=clinic.clinic_name,
            membership_status="pending",
        )

        db.add(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        if exc.orig.args and exc.orig.args[0] == 1062:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists.",
            ) from None

        raise HTTPException(
            status_code=500,
            detail="Unable to submit administrator registration.",
        ) from None
    except Exception:
        db.rollback()
        raise

def resolve_manual_clinic(db: Session, details) -> Clinic:
    # Reuse identical manual submissions without relying on clinic name alone.
    identity = (
        f"{details.clinic_name.casefold()}\n"
        f"{details.address.casefold()}"
    )

    fingerprint = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:32]

    clinic_code = f"MANUAL-{fingerprint}"

    query = select(Clinic).where(
        Clinic.clinic_code == clinic_code
    )

    clinic = db.scalar(query.with_for_update())

    if clinic is None:
        clinic = Clinic(
            clinic_code=clinic_code,
            clinic_name=details.clinic_name,
            address=details.address,
            status="pending",
        )

        try:
            with db.begin_nested():
                db.add(clinic)
                db.flush()
        except IntegrityError:
            clinic = db.scalar(
                query.execution_options(
                    populate_existing=True
                ).with_for_update()
            )

            if clinic is None:
                raise

    if clinic.status not in {"active", "pending"}:
        raise HTTPException(
            status_code=400,
            detail="This clinic is not accepting registrations.",
        )

    return clinic