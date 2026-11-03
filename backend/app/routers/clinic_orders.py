from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.clinic_orders import (
    ClinicOrderListResponse,
    ClinicOrderStatusUpdate,
)
from app.schemas.shop_orders import ShopOrderResponse
from app.services import clinic_order_service


router = APIRouter(
    prefix="/clinic-orders",
    tags=["Clinic Orders"],
)


@router.get(
    "",
    response_model=ClinicOrderListResponse,
)
def list_orders(
    q: str = Query(default="", max_length=100),
    order_status: str | None = Query(
        default=None,
        min_length=1,
        max_length=30,
    ),
    shipping_method: Literal["pickup", "delivery"] | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_order_service.list_clinic_orders(
        db=db,
        current_user=current_user,
        q=q,
        order_status=order_status,
        shipping_method=shipping_method,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{order_id}",
    response_model=ShopOrderResponse,
)
def get_order(
    order_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_order_service.get_clinic_order(
        db=db,
        current_user=current_user,
        order_id=order_id,
    )

@router.post(
    "/{order_id}/status",
    response_model=ShopOrderResponse,
)
def update_status(
    data: ClinicOrderStatusUpdate,
    order_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_order_service.update_order_status(
        db=db,
        current_user=current_user,
        order_id=order_id,
        data=data,
    )