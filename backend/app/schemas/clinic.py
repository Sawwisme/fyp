from decimal import Decimal
from app.states import MALAYSIAN_STATES
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class ClinicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinic_id: int
    clinic_code: str
    clinic_name: str
    address: str | None
    phone_number: str | None
    email: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    status: str
    state: str | None = None


class ClinicUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    address: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = Field(default=None, max_length=255)

    latitude: Decimal | None = Field(
        default=None,
        ge=-90,
        le=90,
        max_digits=9,
        decimal_places=6,
    )
    longitude: Decimal | None = Field(
        default=None,
        ge=-180,
        le=180,
        max_digits=9,
        decimal_places=6,
    )
    state: str | None = Field(default=None, max_length=50)

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, value):
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError("Select a valid Malaysian state.")

        value = value.strip()

        if not value:
            return None

        if value not in MALAYSIAN_STATES:
            raise ValueError("Select a valid Malaysian state.")

        return value

    @field_validator("clinic_name", mode="before")
    @classmethod
    def validate_name(cls, value):
        if value is None:
            raise ValueError("Clinic name cannot be null")

        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError("Clinic name cannot be blank")

        return value

    @field_validator("address", "phone_number", "email", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            return value.strip() or None

        return value