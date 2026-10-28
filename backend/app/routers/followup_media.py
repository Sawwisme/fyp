from fastapi import APIRouter, Depends, Path
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.services import followup_media_service


router = APIRouter(
    prefix="/followup-media",
    tags=["Follow-up Photos"],
)


@router.get("/{image_id}")
def get_photo(
    image_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner", "veterinarian")
    ),
    db: Session = Depends(get_db),
):
    target = followup_media_service.get_photo_path(
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