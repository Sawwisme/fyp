from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.product_recommendation_rules import (
    validate_recommendation_tags,
)

class ProductCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    category_name: str
    clinic_id: int | None


class ProductCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    category_id: int = Field(ge=1, le=2147483647)
    product_name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=5000)

    price: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
    )
    stock_quantity: int = Field(ge=0, le=1000000)
    status: Literal["active", "inactive"] = "inactive"

    target_species: Literal[
        "unknown", "cat", "dog", "both"
    ] = "unknown"

    minimum_age_months: int | None = Field(
        default=None,
        ge=0,
        le=600,
        strict=True,
    )

    suitability_notes: str | None = Field(
        default=None,
        max_length=1000,
    )
    recommendation_enabled: bool = False
    recommendation_tags: list[str] = Field(
        default_factory=list,
        max_length=3,
    )

    @field_validator("recommendation_tags")
    @classmethod
    def check_recommendation_tags(cls, value):
        return validate_recommendation_tags(value)


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    clinic_id: int
    category_id: int
    category: ProductCategoryResponse
    product_name: str
    description: str | None
    price: Decimal
    stock_quantity: int
    image_url: str | None
    status: str
    created_at: datetime
    updated_at: datetime | None
    version: int
    target_species: str
    minimum_age_months: int | None
    suitability_notes: str | None
    recommendation_enabled: bool
    recommendation_tags: list[str] | None = None

class ProductUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expected_version: int = Field(ge=1, le=2147483647)
    category_id: int = Field(ge=1, le=2147483647)
    product_name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=5000)

    price: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
    )

    status: Literal["active", "inactive"]

    target_species: Literal[
        "unknown", "cat", "dog", "both"
    ] = "unknown"

    minimum_age_months: int | None = Field(
        default=None,
        ge=0,
        le=600,
        strict=True,
    )

    suitability_notes: str | None = Field(
        default=None,
        max_length=1000,
    )

    recommendation_enabled: bool = False
    recommendation_tags: list[str] = Field(
        default_factory=list,
        max_length=3,
    )

    @field_validator("recommendation_tags")
    @classmethod
    def check_recommendation_tags(cls, value):
        return validate_recommendation_tags(value)

class ProductStockAdjustment(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expected_version: int = Field(ge=1, le=2147483647)
    quantity_change: int = Field(
        ge=-1000000,
        le=1000000,
    )
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator("quantity_change")
    @classmethod
    def reject_zero(cls, value):
        if value == 0:
            raise ValueError("Enter a non-zero stock adjustment.")
        return value


class ProductStockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    movement_id: int
    product_id: int
    created_by_user_id: int | None
    quantity_change: int
    quantity_before: int
    quantity_after: int
    reason: str
    created_at: datetime

class ProductCategoryCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    category_name: str = Field(
        min_length=2,
        max_length=100,
    )

    description: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("category_name", mode="before")
    @classmethod
    def normalize_category_name(cls, value):
        if isinstance(value, str):
            return " ".join(value.split())
        return value