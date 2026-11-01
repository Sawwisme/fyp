from typing import Literal
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Path,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.products import (
    ProductCategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    ProductStockAdjustment,
    ProductStockMovementResponse,
)
from app.services import product_service, product_image_service


router = APIRouter(
    prefix="/clinic-products",
    tags=["Clinic Products"],
)


@router.get(
    "/categories",
    response_model=list[ProductCategoryResponse],
)
def list_categories(
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return product_service.list_categories(
        db,
        current_user,
    )


@router.get(
    "",
    response_model=list[ProductResponse],
)
def list_products(
    q: str = Query(default="", max_length=100),
    product_status: Literal["active", "inactive"] | None = None,
    category_id: int | None = Query(
        default=None,
        ge=1,
        le=2147483647,
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return product_service.list_clinic_products(
        db,
        current_user,
        q,
        product_status,
        category_id,
        offset,
        limit,
    )


@router.post(
    "",
    response_model=ProductResponse,
    status_code=201,
)
def create_product(
    data: ProductCreate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return product_service.create_product(
        db,
        current_user,
        data,
    )

@router.get(
    "/summary",
    response_model=dict[str, int],
)
def get_product_summary(
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return product_service.get_product_summary(
        db,
        current_user,
    )

@router.put(
    "/{product_id}",
    response_model=ProductResponse,
)
def update_product(
    data: ProductUpdate,
    product_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return product_service.update_product(
        db,
        current_user,
        product_id,
        data,
    )

@router.post(
    "/{product_id}/stock-adjustments",
    response_model=ProductResponse,
    status_code=201,
)
def adjust_product_stock(
    data: ProductStockAdjustment,
    product_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return product_service.adjust_product_stock(
        db,
        current_user,
        product_id,
        data,
    )


@router.get(
    "/{product_id}/stock-history",
    response_model=list[ProductStockMovementResponse],
)
def list_product_stock_history(
    product_id: int = Path(ge=1, le=2147483647),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return product_service.list_product_stock_history(
        db,
        current_user,
        product_id,
        offset,
        limit,
    )

@router.post(
    "/{product_id}/image",
    response_model=ProductResponse,
)
def upload_product_image(
    product_id: int = Path(ge=1, le=2147483647),
    expected_version: int = Form(ge=1, le=2147483647),
    file: UploadFile = File(...),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    try:
        return product_image_service.upload_product_image(
            db,
            current_user,
            product_id,
            expected_version,
            file,
        )
    finally:
        file.file.close()


@router.get("/images/{filename}")
def get_product_image(
    filename: str = Path(
        pattern=r"^[a-f0-9]{32}\.jpg$",
    ),
):
    target = product_image_service.get_product_image_path(
        filename
    )

    return FileResponse(
        path=target,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )