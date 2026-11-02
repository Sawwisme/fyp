from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.shop_orders import (
    ShopOrderCreate,
    ShopOrderResponse,
)
from app.services import shop_order_service
from app.services import order_reservation_service


router = APIRouter(
    prefix="/shop",
    tags=["Owner Shop Orders"],
)


@router.post(
    "/clinics/{clinic_id}/orders",
    response_model=ShopOrderResponse,
    status_code=201,
)
def create_order(
    data: ShopOrderCreate,
    clinic_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return shop_order_service.create_order(
        db,
        current_user,
        clinic_id,
        data,
    )


@router.get(
    "/orders/by-checkout-key/{checkout_key}",
    response_model=ShopOrderResponse,
)
def get_order_by_checkout_key(
    checkout_key: UUID,
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return shop_order_service.get_my_order_by_key(
        db,
        current_user,
        str(checkout_key),
    )


@router.get(
    "/orders",
    response_model=list[ShopOrderResponse],
)
def list_orders(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return shop_order_service.list_my_orders(
        db,
        current_user,
        offset,
        limit,
    )


@router.get(
    "/orders/{order_id}",
    response_model=ShopOrderResponse,
)
def get_order(
    order_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return shop_order_service.get_my_order(
        db,
        current_user,
        order_id,
    )

@router.post("/orders/{order_id}/cancel")
def cancel_unpaid_order(
    order_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return order_reservation_service.cancel_my_unpaid_order(
        db,
        current_user,
        order_id,
    )