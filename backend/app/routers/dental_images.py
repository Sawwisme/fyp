from fastapi import APIRouter, Depends, File, Path, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.services import dental_image_service


router = APIRouter(
    prefix="/dental-images",
    tags=["Dental Images"],
)


@router.post("/pets/{pet_id}", status_code=201)
def upload_dental_image(
    pet_id: int = Path(ge=1, le=2147483647),
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return dental_image_service.upload_image(
        db,
        current_user,
        pet_id,
        file,
    )


@router.get("/{image_id}/file")
def get_dental_image(
    image_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    target = dental_image_service.get_image_path(
        db,
        current_user,
        image_id,
    )

    return FileResponse(
        path=target,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )