from datetime import date, time

from pydantic import BaseModel


class VetAppointmentResponse(BaseModel):
    appointment_id: int
    appointment_date: date
    start_time: time
    end_time: time
    time_slot_id: int

    pet_id: int
    pet_name: str
    owner_name: str

    appointment_type: str
    appointment_source: str | None
    status: str
    ai_analysis_id: int | None = None
    emergency_reason: str | None = None
    urgency_level: str | None = None

    consultation_id: int | None = None
    consultation_status: str | None = None
    needs_rearrangement: bool = False
    medical_history_shared: bool = False

class VetCalendarEntry(BaseModel):
    schedule_id: int
    schedule_date: date
    start_time: time
    end_time: time
    appointment_count: int