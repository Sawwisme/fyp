from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Clinic, Product, ProductCategory, User
from app.services.pet_service import get_owner_profile


def list_shop_clinics(
    db: Session,
    current_user: User,
    q: str,
    offset: int,
    limit: int,
):
    get_owner_profile(db, current_user)

    has_products = (
        select(Product.product_id)
        .where(
            Product.clinic_id == Clinic.clinic_id,
            Product.status == "active",
        )
        .exists()
    )

    statement = select(Clinic).where(
        Clinic.status == "active",
        has_products,
    )

    keyword = q.strip()

    if keyword:
        statement = statement.where(
            Clinic.clinic_name.contains(
                keyword,
                autoescape=True,
            )
        )

    return db.scalars(
        statement
        .order_by(Clinic.clinic_name, Clinic.clinic_id)
        .offset(offset)
        .limit(limit)
    ).all()


def list_shop_categories(
    db: Session,
    current_user: User,
):
    get_owner_profile(db, current_user)

    return db.scalars(
        select(ProductCategory)
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