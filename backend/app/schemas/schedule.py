from datetime import date, time
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    veterinarian_id: int = Field(ge=1, le=2147483647)
    schedule_date: date
    start_time: time
    end_time: time
    slot_minutes: int = Field(default=30, ge=5, le=120)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("Use local clinic time without a timezone")

        if value.second or value.microsecond:
            raise ValueError("Use whole minutes without seconds")

        return value

    @model_validator(mode="after")
    def validate_duration(self):
        start = self.start_time.hour * 60 + self.start_time.minute
        end = self.end_time.hour * 60 + self.end_time.minute

        if end <= start:
            raise ValueError("End time must be later than start time")

        if (end - start) % self.slot_minutes:
            raise ValueError(
                "Schedule duration must divide evenly into the slot length"
            )

        return self


class TimeSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    time_slot_id: int
    start_time: time
    end_time: time
    status: str


class ScheduleResponse(BaseModel):
    schedule_id: int
    veterinarian_id: int
    schedule_date: date
    start_time: time
    end_time: time
    status: str
    time_slots: list[TimeSlotResponse]

class SlotStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available", "blocked"]

class BulkScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    veterinarian_ids: list[int] = Field(
        min_length=1,
        max_length=20,
    )
    start_date: date
    end_date: date
    slot_minutes: int = Field(default=30, ge=5, le=120)

    @field_validator("veterinarian_ids")
    @classmethod
    def validate_veterinarians(cls, values):
        if any(value < 1 or value > 2147483647 for value in values):
            raise ValueError("Invalid veterinarian ID")

        if len(values) != len(set(values)):
            raise ValueError("Do not select a veterinarian twice")

        return sorted(values)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End date must not precede start date")

        if (self.end_date - self.start_date).days > 30:
            raise ValueError("Generate at most 31 days at a time")

        return self


class BulkScheduleResponse(BaseModel):
    created_schedules: int
    created_slots: int
    closed_days: int