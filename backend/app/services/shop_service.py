from fastapi import HTTPException
from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session, selectinload

from app.models import Clinic, Product, ProductCategory, User, Appointment, Consultation
from app.services.pet_service import get_owner_profile
from app.schemas.shop import ShopClinicResponse


def list_shop_clinics(
    db: Session,
    current_user: User,
    q: str,
    offset: int,
    limit: int,
):
    owner = get_owner_profile(db, current_user)

    # Consultation records preserve the clinic where the visit occurred.
    # Each consultation belongs to one unique appointment.
    visits = (
        select(
            Consultation.clinic_id.label("clinic_id"),
            func.count(
                Appointment.appointment_id
            ).label("visit_count"),
            func.max(
                Appointment.appointment_date
            ).label("last_visit_date"),
        )
        .join(
            Appointment,
            Appointment.appointment_id
            == Consultation.appointment_id,
        )
        .where(
            Appointment.pet_owner_id == owner.pet_owner_id,
            Appointment.status == "completed",
            Consultation.status == "completed",
        )
        .group_by(Consultation.clinic_id)
        .subquery()
    )

    has_products = (
        select(Product.product_id)
        .where(
            Product.clinic_id == Clinic.clinic_id,
            Product.status == "active",
            Product.stock_quantity > 0,
        )
        .exists()
    )

    visit_count = func.coalesce(
        visits.c.visit_count,
        0,
    )

    statement = (
        select(
            Clinic,
            visit_count.label("completed_visit_count"),
            visits.c.last_visit_date,
        )
        .outerjoin(
            visits,
            visits.c.clinic_id == Clinic.clinic_id,
        )
        .where(
            Clinic.status == "active",
            or_(
                Clinic.shop_pickup_enabled.is_(True),
                Clinic.shop_delivery_enabled.is_(True),
            ),
            has_products,
        )
    )

    keyword = q.strip()

    if keyword:
        statement = statement.where(
            or_(
                Clinic.clinic_name.contains(
                    keyword,
                    autoescape=True,
                ),
                Clinic.address.contains(
                    keyword,
                    autoescape=True,
                ),
            )
        )

    results = db.execute(
        statement
        .order_by(
            visit_count.desc(),
            visits.c.last_visit_date.desc(),
            Clinic.clinic_name,
            Clinic.clinic_id,
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return [
        ShopClinicResponse(
            clinic_id=clinic.clinic_id,
            clinic_name=clinic.clinic_name,
            address=clinic.address,
            phone_number=clinic.phone_number,
            latitude=(
                float(clinic.latitude)
                if clinic.latitude is not None
                else None
            ),
            longitude=(
                float(clinic.longitude)
                if clinic.longitude is not None
                else None
            ),
            completed_visit_count=int(count),
            last_visit_date=last_visit,
        )
        for clinic, count, last_visit in results
    ]


def list_shop_categories(
    db: Session,
    current_user: User,
    clinic_id: int | None = None,
):
    get_owner_profile(db, current_user)

    if clinic_id is None:
        condition = ProductCategory.clinic_id.is_(None)
    else:
        clinic = db.scalar(
            select(Clinic.clinic_id)
            .where(
                Clinic.clinic_id == clinic_id,
                Clinic.status == "active",
            )
        )

        if clinic is None:
            raise HTTPException(404, "Clinic shop unavailable.")

        condition = or_(
            ProductCategory.clinic_id.is_(None),
            ProductCategory.clinic_id == clinic_id,
        )

    return db.scalars(
        select(ProductCategory)
        .where(condition)
        .order_by(
            ProductCategory.category_name,
            ProductCategory.category_id,
        )
    ).all()


def list_shop_products(
    db: Session,
    current_user: User,
    clinic_id: int,
    q: str,
    category_id: int | None,
    offset: int,
    limit: int,
):
    get_owner_profile(db, current_user)

    clinic = db.scalar(
        select(Clinic.clinic_id)
        .where(
            Clinic.clinic_id == clinic_id,
            Clinic.status == "active",
        )
    )

    if clinic is None:
        raise HTTPException(404, "Clinic shop unavailable.")

    statement = (
        select(Product)
        .options(selectinload(Product.category))
        .where(
            Product.clinic_id == clinic_id,
            Product.status == "active",
        )
    )

    keyword = q.strip()

    if keyword:
        statement = statement.where(
            or_(
                Product.product_name.contains(
                    keyword,
                    autoescape=True,
                ),
                Product.description.contains(
                    keyword,
                    autoescape=True,
                ),
            )
        )

    if category_id is not None:
        statement = statement.where(
            Product.category_id == category_id,
        )

    return db.scalars(
        statement
        .order_by(Product.product_name, Product.product_id)
        .offset(offset)
        .limit(limit)
    ).all()


def get_shop_product(
    db: Session,
    current_user: User,
    product_id: int,
):
    get_owner_profile(db, current_user)

    product = db.scalar(
        select(Product)
        .join(
            Clinic,
            Clinic.clinic_id == Product.clinic_id,
        )
        .options(selectinload(Product.category))
        .where(
            Product.product_id == product_id,
            Product.status == "active",
            Clinic.status == "active",
        )
    )

    if product is None:
        raise HTTPException(404, "Product unavailable.")

    return product