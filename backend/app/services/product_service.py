from fastapi import HTTPException
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload
from datetime import datetime, timezone

from app.models import (
    Clinic,
    Product,
    ProductCategory,
    ProductStockMovement,
    User,
)
from app.schemas.products import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    ProductStockAdjustment,
)
from app.services.admin_profile_service import get_admin_record


def list_categories(
    db: Session,
    current_user: User,
):
    admin = get_admin_record(db, current_user)

    return db.scalars(
        select(ProductCategory)
        .where(
            or_(
                ProductCategory.clinic_id.is_(None),
                ProductCategory.clinic_id == admin.clinic_id,
            )
        )
        .order_by(
            ProductCategory.category_name,
            ProductCategory.category_id,
        )
    ).all()

def list_clinic_products(
    db: Session,
    current_user: User,
    q: str,
    product_status: str | None,
    category_id: int | None,
    offset: int,
    limit: int,
):
    administrator = get_admin_record(db, current_user)

    statement = (
        select(Product)
        .options(selectinload(Product.category))
        .where(
            Product.clinic_id == administrator.clinic_id,
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

    if product_status is not None:
        statement = statement.where(
            Product.status == product_status,
        )

    if category_id is not None:
        statement = statement.where(
            Product.category_id == category_id,
        )

    return db.scalars(
        statement
        .order_by(
            Product.created_at.desc(),
            Product.product_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()


def create_product(
    db: Session,
    current_user: User,
    data: ProductCreate,
):
    try:
        administrator = get_admin_record(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == administrator.clinic_id,
                Clinic.status == "active",
            )
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(403, "Your clinic is unavailable.")

        category = db.scalar(
            select(ProductCategory)
            .where(
                ProductCategory.category_id == data.category_id,
                or_(
                    ProductCategory.clinic_id.is_(None),
                    ProductCategory.clinic_id == clinic.clinic_id,
                ),
            )
        )

        if category is None:
            raise HTTPException(
                422,
                "Select a shared category or one belonging "
                "to your clinic.",
            )

        product = Product(
            clinic_id=clinic.clinic_id,
            category=category,
            product_name=data.product_name,
            description=data.description or None,
            price=data.price,
            stock_quantity=data.stock_quantity,
            status=data.status,
        )

        db.add(product)
        db.flush()

        if product.stock_quantity > 0:
            db.add(
                ProductStockMovement(
                    product_id=product.product_id,
                    created_by_user_id=current_user.user_id,
                    quantity_change=product.stock_quantity,
                    quantity_before=0,
                    quantity_after=product.stock_quantity,
                    reason="Opening stock when product was created.",
                )
            )

        result = ProductResponse.model_validate(product)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise

def get_product_summary(
    db: Session,
    current_user: User,
):
    administrator = get_admin_record(db, current_user)

    counts = db.execute(
        select(
            func.count(Product.product_id).label("total"),
            func.coalesce(
                func.sum(
                    case(
                        (Product.status == "active", 1),
                        else_=0,
                    )
                ),
                0,
            ).label("active"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Product.status == "active")
                            & (Product.stock_quantity > 0)
                            & (Product.stock_quantity <= 5),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("low_stock"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Product.status == "active")
                            & (Product.stock_quantity == 0),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("out_of_stock"),
        )
        .where(
            Product.clinic_id == administrator.clinic_id,
        )
    ).mappings().one()

    return {
        key: int(value or 0)
        for key, value in counts.items()
    }

def update_product(
    db: Session,
    current_user: User,
    product_id: int,
    data: ProductUpdate,
):
    try:
        administrator = get_admin_record(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == administrator.clinic_id,
                Clinic.status == "active",
            )
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(403, "Your clinic is unavailable.")

        product = db.scalar(
            select(Product)
            .where(
                Product.product_id == product_id,
                Product.clinic_id == clinic.clinic_id,
            )
            .options(selectinload(Product.category))
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if product is None:
            raise HTTPException(404, "Product not found.")

        if product.version != data.expected_version:
            raise HTTPException(
                409,
                "This product changed. Reload the catalogue "
                "and reopen the product before editing.",
            )

        category = db.scalar(
            select(ProductCategory)
            .where(
                ProductCategory.category_id == data.category_id,
                or_(
                    ProductCategory.clinic_id.is_(None),
                    ProductCategory.clinic_id == clinic.clinic_id,
                ),
            )
        )

        if category is None:
            raise HTTPException(
                422,
                "Select a shared category or one belonging "
                "to your clinic.",
            )

        product.category = category
        product.product_name = data.product_name
        product.description = data.description or None
        product.price = data.price
        product.status = data.status
        product.version += 1
        product.updated_at = datetime.now(
            timezone.utc
        ).replace(tzinfo=None)

        db.flush()

        result = ProductResponse.model_validate(product)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise

def adjust_product_stock(
    db: Session,
    current_user: User,
    product_id: int,
    data: ProductStockAdjustment,
):
    try:
        administrator = get_admin_record(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == administrator.clinic_id,
                Clinic.status == "active",
            )
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(403, "Your clinic is unavailable.")

        product = db.scalar(
            select(Product)
            .where(
                Product.product_id == product_id,
                Product.clinic_id == clinic.clinic_id,
            )
            .options(selectinload(Product.category))
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if product is None:
            raise HTTPException(404, "Product not found.")

        if product.version != data.expected_version:
            raise HTTPException(
                409,
                "This product changed. Reload the catalogue "
                "and reopen the stock adjustment.",
            )

        before = product.stock_quantity
        after = before + data.quantity_change

        if after < 0:
            raise HTTPException(
                422,
                "The adjustment would make stock negative.",
            )

        if after > 1000000:
            raise HTTPException(
                422,
                "Stock cannot exceed 1,000,000 units.",
            )

        product.stock_quantity = after
        product.version += 1
        product.updated_at = datetime.now(
            timezone.utc
        ).replace(tzinfo=None)

        db.add(
            ProductStockMovement(
                product_id=product.product_id,
                created_by_user_id=current_user.user_id,
                quantity_change=data.quantity_change,
                quantity_before=before,
                quantity_after=after,
                reason=data.reason,
            )
        )

        db.flush()

        result = ProductResponse.model_validate(product)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def list_product_stock_history(
    db: Session,
    current_user: User,
    product_id: int,
    offset: int,
    limit: int,
):
    administrator = get_admin_record(db, current_user)

    product = db.scalar(
        select(Product.product_id)
        .where(
            Product.product_id == product_id,
            Product.clinic_id == administrator.clinic_id,
        )
    )

    if product is None:
        raise HTTPException(404, "Product not found.")

    return db.scalars(
        select(ProductStockMovement)
        .where(
            ProductStockMovement.product_id == product_id,
        )
        .order_by(
            ProductStockMovement.created_at.desc(),
            ProductStockMovement.movement_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()