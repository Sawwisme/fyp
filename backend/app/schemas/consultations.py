from datetime import date, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.clinic_time import CLINIC_TIMEZONE


class TreatmentInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    treatment_id: int | None = Field(
        default=None, ge=1, le=2147483647
    )

    treatment_name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    treatment_date: date
    status: Literal["planned", "completed", "cancelled"]

    @model_validator(mode="after")
    def check_completed_date(self):
        today = datetime.now(CLINIC_TIMEZONE).date()

        if self.status == "completed" and self.treatment_date > today:
            raise ValueError(
                "A completed treatment cannot have a future date"
            )

        return self


class PrescriptionInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    prescription_id: int | None = Field(
        default=None, ge=1, le=2147483647
    )

    medication_name: str = Field(min_length=1, max_length=150)
    dosage: str = Field(min_length=1, max_length=100)
    administration_route: str = Field(min_length=1, max_length=50)
    frequency: str = Field(min_length=1, max_length=100)
    duration: str = Field(min_length=1, max_length=100)
    instructions: str | None = Field(default=None, max_length=5000)


class ConsultationSave(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    version: int = Field(ge=1, le=2147483647)

    consultation_information: str | None = Field(max_length=10000)
    examination_findings: str | None = Field(max_length=10000)
    diagnosis: str | None = Field(max_length=10000)
    notes: str | None = Field(max_length=10000)

    treatments: list[TreatmentInput] = Field(max_length=50)
    prescriptions: list[PrescriptionInput] = Field(max_length=50)

    complete: bool = False

    @model_validator(mode="after")
    def validate_completion(self):
        if self.complete:
            required_fields = {
                "Presenting complaint": self.consultation_information,
                "Examination findings": self.examination_findings,
                "Diagnosis": self.diagnosis,
            }

            for label, value in required_fields.items():
                if not value:
                    raise ValueError(
                        f"{label} is required to complete the consultation"
                    )

        treatment_ids = [
            item.treatment_id
            for item in self.treatments
            if item.treatment_id is not None
        ]

        prescription_ids = [
            item.prescription_id
            for item in self.prescriptions
            if item.prescription_id is not None
        ]

        if len(treatment_ids) != len(set(treatment_ids)):
            raise ValueError("Duplicate treatment IDs")

        if len(prescription_ids) != len(set(prescription_ids)):
            raise ValueError("Duplicate prescription IDs")

        return self


class TreatmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    treatment_id: int
    treatment_name: str
    description: str | None
    treatment_date: date
    status: str


class PrescriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prescription_id: int
    medication_name: str
    dosage: str
    administration_route: str | None
    frequency: str | None
    duration: str | None
    instructions: str | None
    prescription_date: date


class ConsultationResponse(BaseModel):
    consultation_id: int
    appointment_id: int
    clinic_id: int
    pet_id: int
    veterinarian_id: int

    pet_name: str
    owner_name: str

    consultation_date: datetime
    consultation_information: str | None
    examination_findings: str | None
    diagnosis: str | None
    notes: str | None

    status: str
    version: int
    completed_at: datetime | None
    updated_at: datetime

    emergency_reason: str | None
    urgency_level: str | None

    treatments: list[TreatmentResponse]
    prescriptions: list[PrescriptionResponse]