from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class AutomaticSchedulingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    veterinarian_ids: list[int] = Field(
        min_length=1,
        max_length=20,
    )

    enabled: bool
    slot_minutes: int = Field(default=30, ge=5, le=120)
    days_ahead: int = Field(default=30, ge=7, le=30)

    @field_validator("veterinarian_ids")
    @classmethod
    def validate_veterinarian_ids(cls, values):
        if any(value < 1 or value > 2147483647 for value in values):
            raise ValueError("Invalid veterinarian ID")

        if len(values) != len(set(values)):
            raise ValueError("Do not select a veterinarian twice")

        return sorted(values)


class AutomaticSchedulingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    veterinarian_id: int
    enabled: bool
    slot_minutes: int
    days_ahead: int
    last_run_at: datetime | None
    last_error: str | None


class AutomaticGenerationResult(BaseModel):
    created_schedules: int
    created_slots: int
    preserved_days: int