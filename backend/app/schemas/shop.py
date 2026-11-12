from decimal import Decimal
from datetime import date
from pydantic import BaseModel, ConfigDict

from app.schemas.products import ProductCategoryResponse


class ShopClinicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinic_id: int
    clinic_name: str
    address: str | None
    phone_number: str | None
    latitude: float | None = None
    longitude: float | None = None
    completed_visit_count: int = 0
    last_visit_date: date | None = None


class ShopProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    clinic_id: int
    product_name: str
    description: str | None
    category_id: int
    category: ProductCategoryResponse
    price: Decimal
    stock_quantity: int
    image_url: str | None
    target_species: str
    minimum_age_months: int | None
    suitability_notes: str | None