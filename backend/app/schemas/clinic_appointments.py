from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    planned_treatment_id: int | None = Field(
        default=None, ge=1, le=2147483647
    )

    followup_care_id: int | None = Field(
        default=None, ge=1, le=2147483647
    )

    @model_validator(mode="after")
    def validate_return_visit(self):
        if (
            self.planned_treatment_id is not None
            and self.followup_care_id is not None
        ):
            raise ValueError(
                "Select either a treatment plan or a follow-up task."
            )

        if (
            self.followup_care_id is not None
            and self.appointment_type != "follow_up"
        ):
            raise ValueError(
                "A follow-up task must use the follow_up appointment type."
            )

        return self


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
    planned_treatment_id: int | None
    followup_care_id: int | None

class ClinicAppointmentReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_slot_id: int = Field(ge=1, le=2147483647)

class ReturnVisitCreate(ClinicAppointmentCreate):
    appointment_source: Literal["reception"] = "reception"

    @model_validator(mode="after")
    def require_return_visit_link(self):
        if (
            self.planned_treatment_id is None
            and self.followup_care_id is None
        ):
            raise ValueError(
                "Select a treatment plan or follow-up task."
            )

        return self

class ReturnVisitContext(BaseModel):
    pet_owner_id: int
    pet_id: int
    pet_name: str
    owner_name: str
    veterinarian_id: int
    veterinarian_name: str
    recommended_date: date | None
    existing_appointment_id: int | None