from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import User, Veterinarian, ClinicAdministrator
from app.schemas.staff import VeterinarianCreate, AdministratorCreate
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
        clinic_id=administrator.clinic_id,
        clinic_name=administrator.clinic.clinic_name,
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
    administrator = get_admin_record(db, current_user)

    statement = (
        select(Veterinarian)
        .join(Veterinarian.user)
        .options(joinedload(Veterinarian.user))
        .where(
            User.role == "veterinarian",
            Veterinarian.clinic_id == administrator.clinic_id,
        )
        .order_by(Veterinarian.veterinarian_id.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())

def create_administrator(
    db: Session,
    current_user: User,
    data: AdministratorCreate,
) -> ClinicAdministrator:
    try:
        administrator = get_admin_record(db, current_user)
        email = str(data.email).strip().lower()

        existing_email = db.scalar(
            select(User.user_id).where(
                func.lower(User.email) == email
            )
        )

        if existing_email is not None:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists.",
            )

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

        record = ClinicAdministrator(
            user=user,
            clinic_id=administrator.clinic_id,
            clinic_name=administrator.clinic.clinic_name,
            membership_status="approved",
        )

        db.add(record)
        db.commit()

        db.refresh(record)
        db.refresh(user)

        return record

    except IntegrityError as error:
        db.rollback()

        error_code = getattr(error.orig, "args", (None,))[0]

        if error_code == 1062:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists.",
            ) from None

        raise HTTPException(
            status_code=500,
            detail="Unable to create the administrator account.",
        ) from None

    except Exception:
        db.rollback()
        raise


def list_administrators(
    db: Session,
    current_user: User,
    offset: int,
    limit: int,
) -> list[ClinicAdministrator]:
    administrator = get_admin_record(db, current_user)

    statement = (
        select(ClinicAdministrator)
        .join(ClinicAdministrator.user)
        .options(joinedload(ClinicAdministrator.user))
        .where(
            ClinicAdministrator.clinic_id
            == administrator.clinic_id,
            User.role == "clinic_administrator",
        )
        .order_by(
            ClinicAdministrator.clinic_administrator_id.desc()
        )
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())

def update_veterinarian_status(db, current_user, veterinarian_id, data):
    from app.models import Clinic, Appointment, FollowupCare, Consultation
    try:
        admin = get_admin_record(db, current_user)
        # Same clinic-first lock order as booking creation.
        clinic = db.scalar(select(Clinic).where(
            Clinic.clinic_id == admin.clinic_id,
            Clinic.status == "active",
        ).with_for_update())
        if clinic is None:
            raise HTTPException(403, "Clinic is unavailable.")
        vet = db.scalar(select(Veterinarian).where(
            Veterinarian.veterinarian_id == veterinarian_id,
            Veterinarian.clinic_id == admin.clinic_id,
        ).execution_options(populate_existing=True).with_for_update())
        if vet is None:
            raise HTTPException(404, "Veterinarian not found in your clinic.")
        user = db.scalar(select(User).where(
            User.user_id == vet.user_id,
            User.role == "veterinarian",
        ).execution_options(populate_existing=True).with_for_update())
        if user is None:
            raise HTTPException(404, "Veterinarian account not found.")
        if user.status == data.status:
            db.rollback()
            return {"veterinarian_id": vet.veterinarian_id, "status": user.status}
        if user.status != data.expected_status:
            raise HTTPException(409, "Account status changed. Refresh the staff list.")
        if user.status not in ("active", "inactive"):
            raise HTTPException(409, "This account requires separate administrative review.")
        if data.status == "active" and vet.approval_status != "approved":
            raise HTTPException(409, "Only an approved veterinarian can be reactivated.")
        if data.status == "inactive":
            blockers = []
            appointments = db.scalar(select(func.count()).select_from(Appointment).where(
                Appointment.veterinarian_id == veterinarian_id,
                Appointment.status.notin_(["completed", "cancelled", "rejected", "expired"])))
            followups = db.scalar(select(func.count()).select_from(FollowupCare).where(
                FollowupCare.veterinarian_id == veterinarian_id,
                FollowupCare.status.notin_(["completed", "cancelled"])))
            drafts = db.scalar(select(func.count()).select_from(Consultation).where(
                Consultation.veterinarian_id == veterinarian_id,
                Consultation.status != "completed"))
            if appointments: blockers.append(f"{appointments} unresolved appointment(s)")
            if followups: blockers.append(f"{followups} open follow-up(s)")
            if drafts: blockers.append(f"{drafts} unfinished consultation(s)")
            if blockers:
                raise HTTPException(409, "Cannot deactivate: " + ", ".join(blockers) +
                    ". Resolve or reassign this work first. No account changes were saved.")
        user.status = data.status
        db.commit()
        return {"veterinarian_id": veterinarian_id, "status": data.status}
    except Exception:
        db.rollback()
        raise
