from decimal import Decimal
from typing import Literal

from pydantic import field_validator
from app.states import MALAYSIAN_STATES

from app.schemas.cart import CartItemResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.checkout_selection import CheckoutSelection

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

    delivery_states: list[str] = Field(
        default_factory=list,
        max_length=16,
    )

    @field_validator("delivery_states")
    @classmethod
    def validate_delivery_states(cls, values):
        if any(value not in MALAYSIAN_STATES for value in values):
            raise ValueError("Select valid delivery states.")

        return sorted(set(values))

    @model_validator(mode="after")
    def require_fulfilment_method(self):
        if not self.pickup_enabled and not self.delivery_enabled:
            raise ValueError("Enable pickup, delivery, or both.")

        if self.delivery_enabled and not self.delivery_states:
            raise ValueError(
                "Select at least one delivery destination state."
            )
        
        return self


class ShopSettingsResponse(BaseModel):
    clinic_id: int
    clinic_name: str
    pickup_enabled: bool
    delivery_enabled: bool
    delivery_fee: Decimal
    pickup_address: str | None
    version: int
    delivery_states: list[str] = Field(default_factory=list)

class CheckoutQuoteRequest(CheckoutSelection):
    model_config = ConfigDict(extra="forbid")

    expected_cart_version: int = Field(
        ge=0,
        le=2147483647,
        strict=True,
    )
    shipping_method: Literal["pickup", "delivery"]

    delivery_state: str | None = Field(
        default=None,
        max_length=50,
    )


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
    delivery_state: str | None = None