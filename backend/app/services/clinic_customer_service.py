from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Appointment,
    Clinic,
    ClinicOwnerLink,
    Pet,
    PetOwner,
    Schedule,
    TimeSlot,
    User,
    Veterinarian,
)
from app.schemas.clinic_customers import WalkInCustomerCreate
from app.services.admin_profile_service import get_admin_record


def customer_statement(clinic_id):
    linked = (
        select(ClinicOwnerLink.pet_owner_id)
        .where(
            ClinicOwnerLink.clinic_id == clinic_id,
            ClinicOwnerLink.pet_owner_id == PetOwner.pet_owner_id,
        )
        .correlate(PetOwner)
        .exists()
    )

    attended = (
        select(Appointment.appointment_id)
        .join(
            TimeSlot,
            TimeSlot.time_slot_id == Appointment.time_slot_id,
        )
        .join(
            Schedule,
            Schedule.schedule_id == TimeSlot.schedule_id,
        )
        .join(
            Veterinarian,
            Veterinarian.veterinarian_id
            == Schedule.veterinarian_id,
        )
        .where(
            Appointment.pet_owner_id == PetOwner.pet_owner_id,
            Veterinarian.clinic_id == clinic_id,
        )
        .correlate(PetOwner)
        .exists()
    )

    return (
        select(PetOwner)
        .outerjoin(User, User.user_id == PetOwner.user_id)
        .where(or_(linked, attended))
        .options(
            selectinload(PetOwner.user),
            selectinload(PetOwner.pets),
        )
    )


def serialize_customer(owner):
    account = owner.user

    return {
        "pet_owner_id": owner.pet_owner_id,
        "full_name": (
            account.full_name if account else owner.contact_name
        ),
        "phone_number": (
            account.phone_number if account else owner.contact_phone
        ),
        "email": (
            account.email if account else owner.contact_email
        ),
        "address": owner.default_address,
        "has_login_account": account is not None,
        "pets": sorted(owner.pets, key=lambda pet: pet.pet_id),
    }


def search_customers(
    db: Session,
    current_user: User,
    query: str,
    offset: int,
    limit: int,
):
    administrator = get_admin_record(db, current_user)
    query = " ".join(query.split()).lower()

    if len(query) < 2:
        raise HTTPException(
            status_code=400,
            detail="Enter at least 2 characters.",
        )

    name = func.lower(
        func.coalesce(User.full_name, PetOwner.contact_name, "")
    )
    phone = func.coalesce(
        User.phone_number,
        PetOwner.contact_phone,
        "",
    )
    email = func.lower(
        func.coalesce(User.email, PetOwner.contact_email, "")
    )

    statement = (
        customer_statement(administrator.clinic_id)
        .where(
            or_(
                name.contains(query, autoescape=True),
                phone.contains(query, autoescape=True),
                email.contains(query, autoescape=True),
            )
        )
        .order_by(PetOwner.pet_owner_id.desc())
        .offset(offset)
        .limit(limit)
    )

    return [
        serialize_customer(owner)
        for owner in db.scalars(statement).all()
    ]


def create_customer(
    db: Session,
    current_user: User,
    data: WalkInCustomerCreate,
):
    try:
        administrator = get_admin_record(db, current_user)

        # Serialize reception registrations within this clinic.
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

        name = func.lower(
            func.coalesce(User.full_name, PetOwner.contact_name, "")
        )
        phone = func.coalesce(
            User.phone_number,
            PetOwner.contact_phone,
            "",
        )

        existing = db.scalar(
            select(PetOwner.pet_owner_id)
            .join(
                ClinicOwnerLink,
                ClinicOwnerLink.pet_owner_id
                == PetOwner.pet_owner_id,
            )
            .outerjoin(User, User.user_id == PetOwner.user_id)
            .where(
                ClinicOwnerLink.clinic_id == clinic.clinic_id,
                name == data.full_name.lower(),
                phone == data.phone_number,
            )
            .limit(1)
            .with_for_update()
        )

        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "A customer with this name and phone already "
                    "exists in your clinic. Search for them first."
                ),
            )

        owner = PetOwner(
            user_id=None,
            contact_name=data.full_name,
            contact_phone=data.phone_number,
            contact_email=(
                str(data.email) if data.email is not None else None
            ),
            default_address=data.address,
        )

        owner.pets.append(
            Pet(**data.pet.model_dump())
        )

        db.add(owner)
        db.flush()

        db.add(
            ClinicOwnerLink(
                clinic_id=clinic.clinic_id,
                pet_owner_id=owner.pet_owner_id,
                created_by_user_id=current_user.user_id,
            )
        )

        db.commit()
        db.refresh(owner)

        return serialize_customer(owner)

    except Exception:
        db.rollback()
        raise