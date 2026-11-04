from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    decision: Literal["approved", "rejected"]

    review_notes: str = Field(
        min_length=5,
        max_length=1000,
    )

class CashRefundConfirm(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expected_version: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )

    cash_returned: bool = Field(strict=True)

    notes: str = Field(
        min_length=5,
        max_length=500,
    )

class OnlineRefundProcess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )

class RefundStockItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )

    quantity: int = Field(
        ge=1,
        le=1000000,
        strict=True,
    )


class RefundStockReview(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expected_version: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )

    confirmed: bool = Field(strict=True)

    notes: str = Field(
        min_length=5,
        max_length=1000,
    )

    items: list[RefundStockItem] = Field(
        max_length=50,
    )

    @model_validator(mode="after")
    def validate_review(self):
        if not self.confirmed:
            raise ValueError(
                "Confirm that the stock decision has been checked."
            )

        product_ids = [
            item.product_id
            for item in self.items
        ]

        if len(product_ids) != len(set(product_ids)):
            raise ValueError(
                "Each product can appear only once."
            )

        return self