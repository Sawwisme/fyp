from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.user import UserResponse


class AdminProfileResponse(BaseModel):
    clinic_administrator_id: int
    clinic_name: str
    user: UserResponse


class AdminProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    phone_number: str | None = Field(default=None, max_length=20)
    clinic_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )

    @field_validator("full_name", "clinic_name", mode="before")
    @classmethod
    def validate_required_text(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")

        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError("This field cannot be blank")

        return value

    @field_validator("phone_number", mode="before")
    @classmethod
    def normalize_phone_number(cls, value):
        if isinstance(value, str):
            return value.strip() or None

        return value