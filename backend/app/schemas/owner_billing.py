from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.schemas.consultation_billing import (
    BillPaymentSummary,
    BillResponse,
)


class OwnerBillSummary(BaseModel):
    consultation_bill_id: int
    consultation_id: int
    clinic_name: str
    pet_name: str
    consultation_date: datetime
    issued_at: datetime
    status: str
    total_amount: Decimal

    @field_validator(
        "consultation_date",
        "issued_at",
    )
    @classmethod
    def include_utc_offset(cls, value):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class OwnerBillList(BaseModel):
    total: int
    items: list[OwnerBillSummary]


class OwnerBillDetail(BaseModel):
    bill: BillResponse
    appointment_id: int
    clinic_name: str
    clinic_address: str | None
    clinic_phone: str | None
    pet_name: str
    payments: list[BillPaymentSummary]