from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.checkout import (
    ShopSettingsResponse,
    ShopSettingsUpdate,
)
from app.services import checkout_service


router = APIRouter(
    prefix="/clinic-shop",
    tags=["Shop Settings"],
)


@router.get(
    "/settings",
    response_model=ShopSettingsResponse,
)
def get_shop_settings(
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return checkout_service.get_admin_shop_settings(
        db,
        current_user,
    )


@router.put(
    "/settings",
    response_model=ShopSettingsResponse,
)
def update_shop_settings(
    data: ShopSettingsUpdate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return checkout_service.update_shop_settings(
        db,
        current_user,
        data,
    )