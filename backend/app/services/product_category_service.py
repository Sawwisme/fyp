from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Clinic, ProductCategory, User
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