from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
)

from app.schemas.user import UserResponse


class VeterinarianCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr = Field(max_length=255)
    password: SecretStr = Field(min_length=8, max_length=72)
    phone_number: str | None = Field(default=None, max_length=20)

    registration_number: str = Field(min_length=1, max_length=50)
    qualification: str | None = Field(default=None, max_length=150)
    specialization: str | None = Field(default=None, max_length=100)
    years_experience: int | None = Field(default=None, ge=0, le=100)

    @field_validator(
        "full_name",
        "registration_number",
        mode="before",
    )
    @classmethod
    def validate_required_text(cls, value):
        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError("This field cannot be blank")

        return value

    @field_validator(
        "phone_number",
        "qualification",
        "specialization",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            return value.strip() or None

        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")

        return value


class VeterinarianResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    veterinarian_id: int
    registration_number: str
    qualification: str | None
    specialization: str | None
    years_experience: int | None
    approval_status: str
    clinic_name: str | None
    user: UserResponse