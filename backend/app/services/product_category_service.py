from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Clinic, Product, ProductCategory, User
from app.schemas.products import (
    ProductCategoryCreate,
    ProductCategoryResponse,
)
from app.services.admin_profile_service import get_admin_record


def create_category(
    db: Session,
    current_user: User,
    data: ProductCategoryCreate,
):
    try:
        admin = get_admin_record(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == admin.clinic_id,
                Clinic.status == "active",
            )
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(403, "Your clinic is unavailable.")

        existing = db.scalar(
            select(ProductCategory)
            .where(
                or_(
                    ProductCategory.clinic_id.is_(None),
                    ProductCategory.clinic_id == clinic.clinic_id,
                ),
                func.lower(ProductCategory.category_name)
                == data.category_name.lower(),
            )
            .order_by(
                ProductCategory.category_scope,
                ProductCategory.category_id,
            )
            .limit(1)
        )

        # Reuse an existing shared or clinic category.
        # This also makes retries safe when a response is lost.
        if existing is not None:
            result = ProductCategoryResponse.model_validate(existing)
            db.commit()
            return result

        category = ProductCategory(
            clinic_id=clinic.clinic_id,
            category_name=data.category_name,
            description=data.description or None,
        )

        db.add(category)
        db.flush()

        result = ProductCategoryResponse.model_validate(category)

        db.commit()
        return result

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "This category already exists. Reload the category list.",
        ) from None

    except Exception:
        db.rollback()
        raise

def manage_category(db, current_user, category_id, data=None):
    try:
        admin = get_admin_record(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == admin.clinic_id,
                Clinic.status == "active",
            )
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(403, "Clinic is unavailable.")

        category = db.scalar(
            select(ProductCategory)
            .where(
                ProductCategory.category_id == category_id,
                ProductCategory.clinic_id == admin.clinic_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if category is None:
            raise HTTPException(
                404,
                "Only categories belonging to your clinic "
                "can be edited or deleted.",
            )

        if data is None:
            used = db.scalar(
                select(Product.product_id)
                .where(Product.category_id == category_id)
                .limit(1)
            )

            if used is not None:
                raise HTTPException(
                    409,
                    "This category is used by products. "
                    "Move those products to another category first.",
                )

            db.delete(category)
            db.commit()
            return {"deleted": True, "category_id": category_id}

        duplicate = db.scalar(
            select(ProductCategory.category_id)
            .where(
                ProductCategory.category_id != category_id,
                or_(
                    ProductCategory.clinic_id == admin.clinic_id,
                    ProductCategory.clinic_id.is_(None),
                ),
                func.lower(ProductCategory.category_name)
                == data.category_name.lower(),
            )
            .limit(1)
        )

        if duplicate is not None:
            raise HTTPException(
                409,
                "A category with this name already exists.",
            )

        category.category_name = data.category_name
        category.description = data.description or None
        db.flush()

        result = ProductCategoryResponse.model_validate(category)
        db.commit()
        return result

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "The category changed or is in use. Refresh and try again.",
        ) from None
    except Exception:
        db.rollback()
        raise