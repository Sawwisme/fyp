import re

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from app.schemas.pet import PetCreate, PetResponse


class WalkInCustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=150)
    phone_number: str = Field(min_length=7, max_length=20)
    email: EmailStr | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=255)

    pet: PetCreate

    @field_validator("full_name", mode="before")
    @classmethod
    def validate_name(cls, value):
        if isinstance(value, str):
            value = " ".join(value.split())

            if not value:
                raise ValueError("Owner name cannot be blank")

        return value

    @field_validator("phone_number", mode="before")
    @classmethod
    def validate_phone(cls, value):
        if not isinstance(value, str):
            raise ValueError("Enter a phone number")

        value = re.sub(r"[\s()-]", "", value)

        if not re.fullmatch(r"\+?[0-9]{7,15}", value):
            raise ValueError(
                "Enter 7–15 digits, optionally starting with +"
            )

        return value

    @field_validator("email", "address", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            return value.strip() or None

        return value


class ClinicCustomerResponse(BaseModel):
    pet_owner_id: int
    full_name: str
    phone_number: str | None
    email: str | None
    address: str | None
    has_login_account: bool
    pets: list[PetResponse]