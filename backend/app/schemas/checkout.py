from decimal import Decimal
from typing import Literal

from app.schemas.cart import CartItemResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShopSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1, le=2147483647)
    pickup_enabled: bool = Field(strict=True)
    delivery_enabled: bool = Field(strict=True)
    delivery_fee: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )

    @model_validator(mode="after")
    def require_fulfilment_method(self):
        if not self.pickup_enabled and not self.delivery_enabled:
            raise ValueError("Enable pickup, delivery, or both.")
        return self


class ShopSettingsResponse(BaseModel):
    clinic_id: int
    clinic_name: str
    pickup_enabled: bool
    delivery_enabled: bool
    delivery_fee: Decimal
    pickup_address: str | None
    version: int

class CheckoutQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_cart_version: int = Field(
        ge=0,
        le=2147483647,
        strict=True,
    )
    shipping_method: Literal["pickup", "delivery"]


class CheckoutQuoteResponse(BaseModel):
    clinic_id: int
    clinic_name: str
    cart_version: int
    settings_version: int
    shipping_method: Literal["pickup", "delivery"]
    pickup_address: str | None
    items: list[CartItemResponse]
    subtotal: Decimal
    shipping_fee: Decimal
    total_amount: Decimal