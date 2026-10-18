from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import User, Veterinarian
from app.schemas.staff import VeterinarianCreate
from app.services.admin_profile_service import get_admin_record
from app.services.auth_service import hash_password


def create_veterinarian(
    db: Session,
    current_user: User,
    data: VeterinarianCreate,
) -> Veterinarian:
    administrator = get_admin_record(db, current_user)

    existing_email = db.scalar(
        select(User.user_id).where(
            User.email == str(data.email)
        )
    )

    if existing_email is not None:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    existing_registration = db.scalar(
        select(Veterinarian.veterinarian_id).where(
            Veterinarian.registration_number
            == data.registration_number
        )
    )

    if existing_registration is not None:
        raise HTTPException(
            status_code=409,
            detail="This veterinarian registration number already exists.",
        )

    user = User(
        full_name=data.full_name,
        email=str(data.email),
        phone_number=data.phone_number,
        password_hash=hash_password(
            data.password.get_secret_value()
        ),
        role="veterinarian",
        status="active",
    )

    veterinarian = Veterinarian(
        user=user,
        registration_number=data.registration_number,
        qualification=data.qualification,
        specialization=data.specialization,
        years_experience=data.years_experience,
        approval_status="approved",
        clinic_name=administrator.clinic_name,
    )

    try:
        db.add(veterinarian)
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        # MySQL duplicate-key error, including concurrent submissions.
        if exc.orig.args and exc.orig.args[0] == 1062:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This email or veterinarian registration number "
                    "already exists."
                ),
            ) from None

        raise HTTPException(
            status_code=500,
            detail="Unable to create the veterinarian account.",
        ) from None
    except Exception:
        db.rollback()
        raise

    db.refresh(user)
    db.refresh(veterinarian)

    return veterinarian


def list_veterinarians(
    db: Session,
    current_user: User,
    offset: int,
    limit: int,
) -> list[Veterinarian]:
    get_admin_record(db, current_user)

    statement = (
        select(Veterinarian)
        .join(Veterinarian.user)
        .options(joinedload(Veterinarian.user))
        .where(User.role == "veterinarian")
        .order_by(Veterinarian.veterinarian_id.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())