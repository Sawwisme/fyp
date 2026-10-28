from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.consultations import PrescriptionResponse


class OwnerTreatment(BaseModel):
    treatment_id: int
    treatment_name: str
    description: str | None
    treatment_date: date
    recorded_status: str
    current_status: str


class OwnerFollowup(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    followup_care_id: int
    recommended_date: date | None
    followup_date: datetime | None
    reason: str | None
    care_instructions: str | None
    status: str
    photos_required: bool
    photo_instructions: str | None
    visit_required: bool


class OwnerMedicalRecord(BaseModel):
    consultation_id: int
    appointment_id: int
    pet_id: int
    pet_name: str
    consultation_date: datetime
    clinic_name: str
    veterinarian_name: str
    diagnosis: str | None
    treatments: list[OwnerTreatment]
    prescriptions: list[PrescriptionResponse]
    followups: list[OwnerFollowup]