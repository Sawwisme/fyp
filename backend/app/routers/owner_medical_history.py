from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.owner_medical_history import OwnerMedicalRecord
from app.services import owner_medical_history_service


router = APIRouter(
    prefix="/owner-medical-history",
    tags=["Owner Medical History"],
)


@router.get("", response_model=list[OwnerMedicalRecord])
def list_medical_history(
    pet_id: int = Query(ge=1, le=2147483647),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return owner_medical_history_service.list_medical_history(
        db,
        current_user,
        pet_id,
        offset,
        limit,
    )