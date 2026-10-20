from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClinicSelectionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    osm_type: Literal["node", "way", "relation"]
    osm_id: int = Field(gt=0, le=9223372036854775807)
    clinic_name: str = Field(min_length=1, max_length=150)
    address: str | None = Field(max_length=255)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class DiscoveredClinic(ClinicSelectionData):
    selection_token: str