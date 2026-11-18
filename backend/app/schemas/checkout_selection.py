from typing import Annotated

from pydantic import BaseModel, Field, field_validator


ProductId = Annotated[
    int,
    Field(strict=True, ge=1, le=2147483647),
]


class CheckoutSelection(BaseModel):
    # None preserves existing whole-cart checkout.
    selected_product_ids: list[ProductId] | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    @field_validator("selected_product_ids")
    @classmethod
    def normalize_selection(cls, value):
        if value is None:
            return None

        if len(value) != len(set(value)):
            raise ValueError("Duplicate selected products.")

        return sorted(value)