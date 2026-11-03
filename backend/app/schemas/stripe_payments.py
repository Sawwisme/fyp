from datetime import datetime, timezone

from pydantic import BaseModel, field_validator


class StripeCheckoutResponse(BaseModel):
    order_id: int
    checkout_url: str
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def include_utc_offset(cls, value):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value