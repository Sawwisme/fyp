from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class OwnerAppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pet_id: int = Field(ge=1, le=2147483647)
    time_slot_id: int = Field(ge=1, le=2147483647)

    appointment_type: Literal[
        "dental_checkup",
        "consultation",
        "follow_up",
    ] = "dental_checkup"

    followup_care_id: int | None = Field(
        default=None,
        ge=1,
        le=2147483647,
    )

    booking_request_id: UUID | None = None

    expected_payment_version: int | None = Field(
        default=None,
        ge=1,
        le=2147483647,
        strict=True,
    )

    expected_deposit_amount: Decimal | None = Field(
        default=None,
        ge=0,
        le=30000,
        max_digits=10,
        decimal_places=2,
    )

    ai_assessment_review_id: int | None = Field(
        default=None,
        ge=1,
        le=2147483647,
    )


class OwnerAppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    appointment_id: int
    pet_id: int
    veterinarian_id: int
    time_slot_id: int
    appointment_date: date
    appointment_type: str
    status: str
    booking_deposit_amount: Decimal
    payment_expires_at: datetime | None
    ai_assessment_review_id: int | None = None

    @field_validator("payment_expires_at")
    @classmethod
    def include_utc_offset(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

class OwnerAppointmentListItem(BaseModel):
    appointment_id: int
    appointment_date: date
    start_time: time
    end_time: time

    pet_id: int
    pet_name: str

    veterinarian_id: int
    veterinarian_name: str

    clinic_id: int
    clinic_name: str
    clinic_address: str | None

    appointment_type: str
    status: str
    has_pending_followup: bool = False
    needs_rearrangement: bool = False
    booking_deposit_amount: Decimal
    payment_expires_at: datetime | None

    @field_validator("payment_expires_at")
    @classmethod
    def include_utc_offset(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

class OwnerAppointmentReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_slot_id: int = Field(ge=1, le=2147483647)

class OwnerBookingCheckoutResponse(BaseModel):
    appointment_id: int
    appointment_status: str
    deposit_amount: Decimal
    payment_status: str
    checkout_status: str
    checkout_url: str | None
    payment_expires_at: datetime | None

    @field_validator("payment_expires_at")
    @classmethod
    def include_utc_offset(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

class OwnerBookingRefundResponse(BaseModel):
    appointment_id: int
    refund_id: int
    status: str
    refund_amount: Decimal
    requested_at: datetime
    processed_at: datetime | None
    refund_purpose: Literal[
        "booking_cancellation",
        "booking_excess",
    ]

    @field_validator("requested_at", "processed_at")
    @classmethod
    def include_utc_offset(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value