from datetime import date, datetime, time

from pydantic import BaseModel


class VeterinarianSummary(BaseModel):
    veterinarian_id: int
    clinic_id: int
    full_name: str
    clinic_name: str | None
    specialization: str | None


class AvailableSlotResponse(BaseModel):
    time_slot_id: int
    schedule_id: int
    veterinarian_id: int
    veterinarian_name: str
    clinic_id: int
    clinic_name: str | None
    schedule_date: date
    start_time: time
    end_time: time

class ClinicSummary(BaseModel):
    clinic_id: int
    clinic_name: str
    address: str | None
    phone_number: str | None
    latitude: float | None
    longitude: float | None
    completed_visit_count: int = 0
    last_visit_at: datetime | None = None