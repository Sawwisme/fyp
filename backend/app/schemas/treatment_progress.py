from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class TreatmentProgressUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    version: int = Field(ge=1, le=2147483647)

    status: Literal["in_progress", "completed", "cancelled"]

    completion_consultation_id: int | None = Field(
        default=None,
        ge=1,
        le=2147483647,
    )

    cancellation_reason: str | None = Field(
        default=None,
        max_length=1000,
    )

    @model_validator(mode="after")
    def validate_action(self):
        if self.status == "completed":
            if self.completion_consultation_id is None:
                raise ValueError(
                    "Select the consultation where treatment "
                    "completion was recorded."
                )
        elif self.completion_consultation_id is not None:
            raise ValueError(
                "A completion consultation is only used "
                "when completing treatment."
            )

        if self.status == "cancelled":
            if (
                not self.cancellation_reason
                or len(self.cancellation_reason) < 5
            ):
                raise ValueError(
                    "Enter a cancellation reason "
                    "of at least 5 characters."
                )
        elif self.cancellation_reason:
            raise ValueError(
                "A cancellation reason is only used "
                "when cancelling treatment."
            )

        return self


class TreatmentProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    treatment_id: int
    status: str
    version: int
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    completion_consultation_id: int | None
    cancellation_reason: str | None
    updated_by_user_id: int | None
    updated_at: datetime | None

class CompletionConsultationOption(BaseModel):
    consultation_id: int
    consultation_date: datetime
    diagnosis: str | None