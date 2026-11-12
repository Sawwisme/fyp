from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.cart import CartQuantityUpdate, CartResponse
from app.services import cart_service


router = APIRouter(
    prefix="/shop/cart",
    tags=["Owner Cart"],
)


@router.get("", response_model=list[CartResponse])
def list_my_carts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return cart_service.list_my_carts(db, current_user, offset, limit)


@router.get(
    "/{clinic_id}",
    response_model=CartResponse,
)
def get_my_cart(
    clinic_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return cart_service.get_my_cart(
        db,
        current_user,
        clinic_id,
    )


@router.put(
    "/{clinic_id}/items/{product_id}",
    response_model=CartResponse,
)
def set_cart_quantity(
    data: CartQuantityUpdate,
    clinic_id: int = Path(ge=1, le=2147483647),
    product_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return cart_service.set_cart_quantity(
        db,
        current_user,
        clinic_id,
        product_id,
        data,
    )