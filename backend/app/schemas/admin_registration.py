from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

class ManualClinicRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_name: str = Field(min_length=1, max_length=150)
    address: str = Field(min_length=1, max_length=255)

    @field_validator("clinic_name", "address", mode="before")
    @classmethod
    def validate_text(cls, value):
        if isinstance(value, str):
            value = " ".join(value.split())

            if not value:
                raise ValueError("This field cannot be blank")

        return value

class AdminRegistrationRequest(BaseModel):
    manual_clinic: ManualClinicRequest | None = None
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr = Field(max_length=255)
    phone_number: str | None = Field(default=None, max_length=20)
    password: SecretStr = Field(min_length=8, max_length=72)
    clinic_id: int | None = Field(
        default=None,
        ge=1,
        le=2147483647,
    )
    selection_token: SecretStr | None = Field(
        default=None,
        min_length=1,
        max_length=16384,
    )

    @model_validator(mode="after")
    def validate_clinic_choice(self):
        choices = sum([
            self.clinic_id is not None,
            self.selection_token is not None,
            self.manual_clinic is not None,
        ])

        if choices != 1:
            raise ValueError(
                "Choose exactly one clinic selection method."
            )

        return self

    @field_validator("full_name", mode="before")
    @classmethod
    def validate_name(cls, value):
        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError("Full name cannot be blank")

        return value

    @field_validator("phone_number", mode="before")
    @classmethod
    def normalize_phone(cls, value):
        if isinstance(value, str):
            return value.strip() or None

        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")

        return value


class RegistrationClinicOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinic_id: int
    clinic_name: str
    address: str | None