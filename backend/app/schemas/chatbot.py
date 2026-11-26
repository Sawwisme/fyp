from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import Literal
from pydantic import field_validator
from app.states import MALAYSIAN_STATES

class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pet_id: int | None = Field(
        default=None,
        ge=1,
        le=2147483647,
    )

class ProductSearchPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: int | None = Field(
        default=None,
        ge=1,
        le=2147483647,
        strict=True,
    )
    state: str | None = Field(default=None, max_length=50)
    fulfilment: Literal["pickup", "delivery"] | None = None

    delivery_state: str | None = Field(default=None, max_length=50)

    @field_validator("state", "delivery_state")
    @classmethod
    def validate_state(cls, value):
        if value is None:
            return None

        if value not in MALAYSIAN_STATES:
            raise ValueError("Select a valid Malaysian state.")

        return value

class MessageCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    client_request_id: UUID

    message: str = Field(
        min_length=1,
        max_length=2000,
    )
    product_preferences: ProductSearchPreferences | None = None

class BookingDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    draft: dict | None = None