from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class BookingPaymentSettingsResponse(BaseModel):
    clinic_id: int
    deposit_amount: Decimal
    version: int


class BookingPaymentSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deposit_amount: Decimal = Field(
        ge=0,
        le=30000,
        max_digits=10,
        decimal_places=2,
    )

    expected_version: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )

    @field_validator("deposit_amount")
    @classmethod
    def validate_deposit_amount(cls, value):
        if Decimal("0") < value < Decimal("1"):
            raise ValueError(
                "Use 0 to disable deposits, "
                "or enter an amount of at least RM 1."
            )

        return value.quantize(Decimal("0.01"))