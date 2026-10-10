from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    email: str
    phone_number: str | None
    role: str
    status: str
    created_at: datetime
    updated_at: datetime | None