from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Clinic, Product, User
from app.schemas.products import ProductResponse
from app.services.admin_profile_service import get_admin_record
from app.services.followup_uploads import prepare_photo


PRODUCT_IMAGE_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "public_uploads"
    / "products"
)


def upload_product_image(
    db: Session,
    current_user: User,
    product_id: int,
    expected_version: int,
    upload: UploadFile,
):
    target = None
    committing = False

    try:
        administrator = get_admin_record(db, current_user)

        # Reuse validation only; product photos use their own directory.
        content = prepare_photo(upload)

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

        if product.version != expected_version:
            raise HTTPException(
                409,
                "This product changed. Reload the catalogue "
                "before uploading its photo.",
            )

        PRODUCT_IMAGE_DIRECTORY.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = f"{uuid4().hex}.jpg"
        target = PRODUCT_IMAGE_DIRECTORY / filename

        with target.open("xb") as output:
            output.write(content)

        product.image_url = f"/clinic-products/images/{filename}"
        product.version += 1
        product.updated_at = datetime.now(
            timezone.utc
        ).replace(tzinfo=None)

        db.flush()
        result = ProductResponse.model_validate(product)

        committing = True
        db.commit()

        return result

    except Exception:
        db.rollback()

        # Retain the file if the commit result is uncertain.
        if target is not None and not committing:
            target.unlink(missing_ok=True)

        raise


def get_product_image_path(filename: str):
    target = PRODUCT_IMAGE_DIRECTORY / filename

    if not target.is_file():
        raise HTTPException(404, "Product image not found.")

    return target