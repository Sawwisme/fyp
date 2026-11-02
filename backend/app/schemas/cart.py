from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CartQuantityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(
        ge=0,
        le=2147483647,
        strict=True,
    )
    quantity: int = Field(ge=0, le=99, strict=True)


class CartItemResponse(BaseModel):
    product_id: int
    product_name: str
    image_url: str | None
    quantity: int
    stock_quantity: int
    unit_price: Decimal
    line_total: Decimal
    available: bool
    price_changed: bool


class CartResponse(BaseModel):
    cart_id: int | None
    clinic_id: int
    clinic_name: str
    version: int
    items: list[CartItemResponse]
    item_count: int
    total_quantity: int
    subtotal: Decimal
    can_checkout: bool