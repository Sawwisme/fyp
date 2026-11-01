from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.products import ProductCategoryResponse
from app.schemas.shop import ShopClinicResponse, ShopProductResponse
from app.services import shop_service


router = APIRouter(
    prefix="/shop",
    tags=["Owner Shop"],
)


@router.get(
    "/clinics",
    response_model=list[ShopClinicResponse],
)
def list_shop_clinics(
    q: str = Query(default="", max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return shop_service.list_shop_clinics(
        db, current_user, q, offset, limit
    )


@router.get(
    "/categories",
    response_model=list[ProductCategoryResponse],
)
def list_shop_categories(
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return shop_service.list_shop_categories(db, current_user)


@router.get(
    "/clinics/{clinic_id}/products",
    response_model=list[ShopProductResponse],
)
def list_shop_products(
    clinic_id: int = Path(ge=1, le=2147483647),
    q: str = Query(default="", max_length=100),
    category_id: int | None = Query(
        default=None, ge=1, le=2147483647
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return shop_service.list_shop_products(
        db,
        current_user,
        clinic_id,
        q,
        category_id,
        offset,
        limit,
    )


@router.get(
    "/products/{product_id}",
    response_model=ShopProductResponse,
)
def get_shop_product(
    product_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return shop_service.get_shop_product(
        db,
        current_user,
        product_id,
    )