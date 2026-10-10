from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

class PetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pet_name: str = Field(min_length=1, max_length=100)
    species: Literal["cat", "dog"]
    breed: str | None = Field(default=None, max_length=100)
    gender: Literal["male", "female", "unknown"] | None = None
    date_of_birth: date | None = None
    weight: Decimal | None = Field(
        default=None,
        gt=0,
        le=Decimal("999.99"),
        max_digits=5,
        decimal_places=2,
    )
    colour: str | None = Field(default=None, max_length=50)
    existing_dental_condition: str | None = Field(
        default=None,
        max_length=10000,
    )
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("pet_name")
    @classmethod
    def validate_pet_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Pet name cannot be blank")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value


class PetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pet_id: int
    pet_owner_id: int
    pet_name: str
    species: str
    breed: str | None
    gender: str | None
    date_of_birth: date | None
    weight: Decimal | None
    colour: str | None
    existing_dental_condition: str | None
    notes: str | None

class PetUpdate(PetCreate):
    pet_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    species: Literal["cat", "dog"] | None = None

    @field_validator("pet_name")
    @classmethod
    def validate_pet_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Pet name cannot be null")

        value = value.strip()
        if not value:
            raise ValueError("Pet name cannot be blank")

        return value

    @field_validator("species")
    @classmethod
    def validate_species(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Species cannot be null")

        return value