from datetime import date, time

from pydantic import BaseModel


class VeterinarianSummary(BaseModel):
    veterinarian_id: int
    full_name: str
    clinic_name: str | None
    specialization: str | None


class AvailableSlotResponse(BaseModel):
    time_slot_id: int
    schedule_id: int
    veterinarian_id: int
    veterinarian_name: str
    clinic_name: str | None
    schedule_date: date
    start_time: time
    end_time: time