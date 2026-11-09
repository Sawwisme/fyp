from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AIAssessmentReviewRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    clinic_id: int = Field(
        ge=1,
        le=2147483647,
    )
    owner_message: str | None = Field(
        default=None,
        max_length=2000,
    )


class AIAssessmentReviewSubmit(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    reviewed_severity: Literal[
        "none",
        "mild",
        "moderate",
        "severe",
        "unable_to_assess",
    ]

    recommended_action: Literal[
        "routine_booking",
        "prompt_clinic_assessment",
        "home_care",
        "unable_to_assess",
    ]

    feedback: str = Field(
        min_length=1,
        max_length=5000,
    )