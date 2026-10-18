from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.staff import VeterinarianResponse


class VetProfileResponse(VeterinarianResponse):
    pass


class VetProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    phone_number: str | None = Field(default=None, max_length=20)

    @field_validator("full_name", mode="before")
    @classmethod
    def validate_full_name(cls, value):
        if value is None:
            raise ValueError("Full name cannot be null")

        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError("Full name cannot be blank")

        return value

    @field_validator("phone_number", mode="before")
    @classmethod
    def normalize_phone_number(cls, value):
        if isinstance(value, str):
            return value.strip() or None

        return value