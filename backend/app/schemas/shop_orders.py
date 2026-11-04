from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ShopOrderCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    checkout_key: UUID

    expected_cart_version: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )
    expected_settings_version: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )
    expected_total_amount: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
    )

    shipping_method: Literal["pickup", "delivery"]

    payment_method: Literal["cash", "online_banking"] = "online_banking"

    recipient_name: str = Field(
        min_length=2,
        max_length=150,
    )
    recipient_phone: str = Field(
        min_length=7,
        max_length=20,
        pattern=r"^\+?[0-9][0-9 ()-]{5,18}[0-9]$",
    )
    delivery_address: str | None = Field(
        default=None,
        min_length=10,
        max_length=500,
    )
    owner_note: str | None = Field(
        default=None,
        max_length=500,
    )

    @model_validator(mode="after")
    def require_delivery_address(self):
        if self.shipping_method == "delivery":
            if not self.delivery_address:
                raise ValueError("Enter the delivery address.")

            if self.payment_method == "cash":
                raise ValueError(
                    "Cash payment is available for clinic pickup only."
                )

        return self

class ShopOrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class ShopOrderResponse(BaseModel):
    order_id: int
    clinic_id: int
    clinic_name: str
    order_status: str
    payment_status: str
    payment_method: str

    shipping_method: str
    shipping_address: str
    recipient_name: str
    recipient_phone: str
    owner_note: str | None

    subtotal: Decimal
    shipping_fee: Decimal
    total_amount: Decimal

    checkout_key: UUID
    version: int

    order_date: datetime
    payment_expires_at: datetime | None
    items: list[ShopOrderItemResponse]

    @field_validator("order_date", "payment_expires_at")
    @classmethod
    def include_utc_offset(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value