from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pet_id: int | None = Field(
        default=None,
        ge=1,
        le=2147483647,
    )


class MessageCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    client_request_id: UUID

    message: str = Field(
        min_length=1,
        max_length=2000,
    )