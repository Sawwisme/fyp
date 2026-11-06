from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class BillItemInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    item_type: Literal[
        "consultation",
        "procedure",
        "medication",
        "other",
    ]

    description: str = Field(
        min_length=2,
        max_length=255,
    )

    quantity: int = Field(
        ge=1,
        le=999,
        strict=True,
    )

    unit_price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )


class BillDraftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[BillItemInput] = Field(
        min_length=1,
        max_length=50,
    )


class BillDraftUpdate(BillDraftCreate):
    expected_version: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )


class BillItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consultation_bill_item_id: int
    item_type: str
    description: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal

class BillDepositRefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    refund_id: int
    status: str
    refund_amount: Decimal
    requested_at: datetime
    processed_at: datetime | None

    @field_validator("requested_at", "processed_at")
    @classmethod
    def include_utc_offset(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

class BillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consultation_bill_id: int
    consultation_id: int
    clinic_id: int
    pet_owner_id: int
    status: str
    total_amount: Decimal
    deposit_paid_amount: Decimal
    deposit_applied_amount: Decimal
    deposit_excess_refund_amount: Decimal
    deposit_refund: BillDepositRefundResponse | None = None
    balance_amount: Decimal
    amount_due: Decimal
    version: int
    created_at: datetime
    updated_at: datetime
    issued_at: datetime | None
    items: list[BillItemResponse]

    @field_validator(
        "created_at",
        "updated_at",
        "issued_at",
    )
    @classmethod
    def include_utc_offset(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

class BillIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )


class BillingConsultationSummary(BaseModel):
    consultation_id: int
    appointment_id: int
    pet_name: str
    owner_name: str
    consultation_date: datetime

    consultation_bill_id: int | None
    bill_status: str
    total_amount: Decimal | None

    @field_validator("consultation_date")
    @classmethod
    def include_utc_offset(cls, value):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class BillingConsultationList(BaseModel):
    total: int
    items: list[BillingConsultationSummary]

class BillCashCollect(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expected_version: int = Field(
        ge=1,
        le=2147483647,
        strict=True,
    )

    expected_amount: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
    )

    cash_received: bool = Field(strict=True)

    notes: str | None = Field(
        default=None,
        max_length=500,
    )


class BillCashReceipt(BaseModel):
    bill: BillResponse
    payment_id: int
    receipt_number: str
    amount: Decimal
    payment_date: datetime

    @field_validator("payment_date")
    @classmethod
    def include_utc_offset(cls, value):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

class BillPaymentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: int
    payment_method: str
    payment_status: str
    amount: Decimal
    payment_date: datetime | None
    receipt_number: str | None

    @field_validator("payment_date")
    @classmethod
    def include_utc_offset(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value