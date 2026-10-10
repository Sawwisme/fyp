from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.user import UserResponse


class OwnerProfileResponse(BaseModel):
    pet_owner_id: int
    default_address: str | None
    user: UserResponse


class OwnerProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    phone_number: str | None = Field(default=None, max_length=20)
    default_address: str | None = Field(default=None, max_length=255)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Full name cannot be null")

        value = value.strip()
        if not value:
            raise ValueError("Full name cannot be blank")

        return value