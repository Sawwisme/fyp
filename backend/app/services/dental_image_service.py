import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.models import DentalImage, Pet
from app.services.pet_service import get_pet, get_owner_profile
from app.services.followup_uploads import prepare_photo


UPLOAD_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "private_uploads"
    / "dental_images"
)


def upload_image(db, current_user, pet_id, upload):
    # An owner may upload only for their own pet.
    get_pet(db, current_user, pet_id)

    # Checks the actual image, removes metadata and converts to JPEG.
    # Uses the existing 8 MB upload limit.
    content = prepare_photo(upload)

    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}.jpg"
    target = UPLOAD_DIRECTORY / filename
    created = False

    try:
        with target.open("xb") as output:
            created = True
            output.write(content)

        image = DentalImage(
            pet_id=pet_id,
            uploaded_by=current_user.user_id,
            image_url=filename,
        )

        db.add(image)
        db.flush()

        response = {
            "dental_image_id": image.dental_image_id,
            "pet_id": image.pet_id,
            "status": "uploaded",
            "image_url": (
                f"/dental-images/{image.dental_image_id}/file"
            ),
        }

        db.commit()
        return response

    except Exception:
        db.rollback()

        if created:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass

        raise


def get_image_path(db, current_user, image_id):
    owner = get_owner_profile(db, current_user)

    image = db.scalar(
        select(DentalImage)
        .join(Pet, Pet.pet_id == DentalImage.pet_id)
        .where(
            DentalImage.dental_image_id == image_id,
            DentalImage.uploaded_by == current_user.user_id,
            Pet.pet_owner_id == owner.pet_owner_id,
        )
    )

    if image is None:
        raise HTTPException(404, "Dental image not found.")

    if not re.fullmatch(r"[0-9a-f]{32}\.jpg", image.image_url):
        raise HTTPException(404, "Dental image not available.")

    directory = UPLOAD_DIRECTORY.resolve()
    target = (directory / image.image_url).resolve()

    if target.parent != directory or not target.is_file():
        raise HTTPException(404, "Dental image file not found.")

    return target