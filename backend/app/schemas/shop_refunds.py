from datetime import datetime, timezone
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class ShopRefundCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    reason: str = Field(
        min_length=5,
        max_length=1000,
    )


class ShopRefundResponse(BaseModel):
    refund_id: int
    order_id: int
    refund_amount: Decimal
    reason: str | None
    status: str
    version: int
    review_notes: str | None
    requested_at: datetime
    reviewed_at: datetime | None
    processed_at: datetime | None
    stock_reviewed_at: datetime | None = None
    stock_return_items: list[dict[str, int]] | None = None

    @field_validator(
        "requested_at",
        "reviewed_at",
        "processed_at",
        "stock_reviewed_at",
    )
    @classmethod
    def include_utc_offset(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

class ClinicRefundReview(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expected_version: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )

    approve: bool = Field(strict=True)

    review_notes: str = Field(
        min_length=5,
        max_length=1000,
    )