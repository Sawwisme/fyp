from datetime import date, time

from pydantic import BaseModel


class LinkedVisitSummary(BaseModel):
    appointment_id: int
    appointment_date: date
    start_time: time
    end_time: time
    status: str
    consultation_id: int | None
    consultation_status: str | None