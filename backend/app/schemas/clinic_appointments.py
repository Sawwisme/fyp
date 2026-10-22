from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClinicAppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pet_owner_id: int = Field(ge=1, le=2147483647)
    pet_id: int = Field(ge=1, le=2147483647)
    time_slot_id: int = Field(ge=1, le=2147483647)

    appointment_type: Literal[
        "dental_checkup",
        "consultation",
        "follow_up",
    ] = "dental_checkup"

    appointment_source: Literal[
        "walk_in",
        "reception",
    ] = "walk_in"


class ClinicAppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    appointment_id: int
    pet_owner_id: int
    pet_id: int
    veterinarian_id: int
    time_slot_id: int
    appointment_type: str
    appointment_source: str
    appointment_date: date
    status: str