from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.shop_orders import ShopOrderResponse


class ClinicOrderListResponse(BaseModel):
    total: int
    items: list[ShopOrderResponse]

class ClinicOrderStatusUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expected_version: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )

    new_status: Literal[
        "processing",
        "ready_for_pickup",
        "shipped",
        "completed",
        "cancelled",
    ]

    cash_received: bool = Field(
        default=False,
        strict=True,
    )

    notes: str | None = Field(
        default=None,
        max_length=500,
    )