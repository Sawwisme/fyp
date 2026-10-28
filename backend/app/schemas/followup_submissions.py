from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field


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