from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VetAbsenceCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    absence_date: date
    start_time: time
    end_time: time
    reason: str = Field(min_length=5, max_length=2000)

    @model_validator(mode="after")
    def validate_times(self):
        if (
            self.start_time.tzinfo is not None
            or self.end_time.tzinfo is not None
        ):
            raise ValueError("Enter local Malaysia times without an offset.")

        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time.")

        return self


class VetAbsenceCreated(BaseModel):
    absence_id: int
    affected_appointments: int

class VetAbsenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    absence_id: int
    absence_date: date
    start_time: time
    end_time: time
    reason: str
    status: str

class RearrangementResolve(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expected_time_slot_id: int = Field(ge=1, le=2147483647)
    expected_appointment_status: str = Field(
        min_length=1,
        max_length=20,
    )
    resolution_note: str = Field(min_length=5, max_length=2000)
    owner_agreement_note: str = Field(
        min_length=5,
        max_length=2000,
    )