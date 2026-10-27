from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.linked_visit import LinkedVisitSummary


class FollowupResponse(BaseModel):
    followup_care_id: int
    consultation_id: int
    pet_id: int
    pet_name: str
    owner_name: str
    recommended_date: date | None
    followup_date: datetime | None
    reason: str | None
    care_instructions: str | None
    assessment_information: str | None
    notes: str | None
    status: str
    overdue: bool
    linked_visit: LinkedVisitSummary | None = None

class FollowupReview(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    assessment_information: str = Field(
        min_length=1,
        max_length=10000,
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )


class FollowupCancel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    reason: str = Field(min_length=5, max_length=1000)


class FollowupActionResponse(BaseModel):
    followup_care_id: int
    status: str
    followup_date: datetime | None