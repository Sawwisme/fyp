from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notification_id: int
    notification_type: str
    title: str
    message: str
    resource_type: str
    resource_id: int
    created_at: datetime
    read_at: datetime | None

    @field_validator("created_at", "read_at")
    @classmethod
    def include_utc_offset(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value