from datetime import time

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class WorkingPeriod(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("Use local clinic time without a timezone")

        if value.second or value.microsecond:
            raise ValueError("Use whole minutes without seconds")

        return value

    @model_validator(mode="after")
    def validate_period(self):
        if self.end_time <= self.start_time:
            raise ValueError("End time must be later than start time")

        return self


class WorkingHoursUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    periods: list[WorkingPeriod] = Field(max_length=84)

    @model_validator(mode="after")
    def validate_periods(self):
        ordered = sorted(
            self.periods,
            key=lambda period: (period.weekday, period.start_time),
        )

        for previous, current in zip(ordered, ordered[1:]):
            if (
                previous.weekday == current.weekday
                and previous.end_time > current.start_time
            ):
                raise ValueError("Working periods cannot overlap")

        self.periods = ordered
        return self