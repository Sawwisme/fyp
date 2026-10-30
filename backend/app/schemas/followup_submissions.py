from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field, Field


class FollowupPhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    followup_care_image_id: int
    uploaded_at: datetime
    @computed_field
    @property
    def image_url(self) -> str:
        return (
            f"/followup-media/{self.followup_care_image_id}"
        )


class FollowupSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    submission_id: int
    followup_care_id: int
    owner_comment: str | None
    submitted_at: datetime
    review_status: str
    veterinarian_comment: str | None
    reviewed_at: datetime | None
    images: list[FollowupPhotoResponse]
    decision_outcome: str | None

class FollowupSubmissionReview(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    outcome: Literal[
        "complete",
        "request_update",
        "in_clinic",
    ]

    veterinarian_comment: str = Field(
        min_length=1,
        max_length=5000,
    )
    expected_reviewed_at: datetime | None

    correction_reason: str | None = Field(
    default=None,
    min_length=5,
    max_length=1000,
    )

class OwnerFollowupSubmissionState(BaseModel):
    followup_care_id: int
    followup_status: str
    can_submit: bool
    submission_state: Literal[
        "action_needed",
        "awaiting_review",
        "update_requested",
        "reviewed",
        "completed",
        "cancelled",
    ]

from datetime import date
from app.schemas.owner_medical_history import OwnerFollowup


class OwnerFollowupListItem(OwnerFollowup):
    consultation_id: int
    appointment_id: int
    appointment_date: date
    pet_id: int
    pet_name: str
    clinic_name: str