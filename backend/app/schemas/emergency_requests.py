from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class EmergencyRequestCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    clinic_id: int = Field(ge=1, le=2147483647)
    pet_id: int = Field(ge=1, le=2147483647)
    emergency_reason: str = Field(min_length=10, max_length=3000)


class EmergencyRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    emergency_appointment_id: int
    clinic_id: int
    pet_owner_id: int
    pet_id: int

    emergency_reason: str
    urgency_level: str
    approval_status: str

    appointment_id: int | None
    assigned_veterinarian_id: int | None

    created_at: datetime
    reviewed_at: datetime | None
    rejection_reason: str | None


class EmergencyRequestListItem(EmergencyRequestResponse):
    clinic_name: str
    pet_name: str
    owner_name: str
    owner_phone: str | None

class EmergencyRequestApprove(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_slot_id: int = Field(ge=1, le=2147483647)
    urgency_level: Literal["urgent", "critical"] = "urgent"

class EmergencyRequestReject(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    rejection_reason: str = Field(min_length=5, max_length=1000)