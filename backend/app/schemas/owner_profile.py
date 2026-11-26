from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.user import UserResponse
from app.states import MALAYSIAN_STATES

class OwnerProfileResponse(BaseModel):
    pet_owner_id: int
    default_address: str | None
    user: UserResponse
    default_state: str | None = None


class OwnerProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    phone_number: str | None = Field(default=None, max_length=20)
    default_address: str | None = Field(default=None, max_length=255)

    default_state: str | None = Field(default=None, max_length=50)

    @field_validator("default_state")
    @classmethod
    def validate_default_state(cls, value):
        if value is None:
            return None

        value = value.strip()
        if not value:
            return None

        if value not in MALAYSIAN_STATES:
            raise ValueError("Select a valid Malaysian state.")

        return value

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Full name cannot be null")

        value = value.strip()
        if not value:
            raise ValueError("Full name cannot be blank")

        return value