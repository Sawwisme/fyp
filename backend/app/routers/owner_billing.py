from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.owner_billing import (
    OwnerBillDetail,
    OwnerBillList,
)
from app.services import owner_billing_service


router = APIRouter(
    prefix="/owner-billing",
    tags=["Owner Consultation Bills"],
)


@router.get(
    "/bills",
    response_model=OwnerBillList,
)
def list_my_bills(
    bill_status: Literal["issued", "paid", "void"] | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return owner_billing_service.list_my_bills(
        db,
        current_user,
        bill_status,
        offset,
        limit,
    )


@router.get(
    "/bills/{bill_id}",
    response_model=OwnerBillDetail,
)
def get_my_bill(
    bill_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return owner_billing_service.get_my_bill(
        db,
        current_user,
        bill_id,
    )