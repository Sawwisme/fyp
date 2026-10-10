from sqlalchemy import Column, ForeignKey, Integer, String, Time
from sqlalchemy.orm import relationship

from app.database import Base


class TimeSlot(Base):
    __tablename__ = "time_slots"

    time_slot_id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(
        Integer,
        ForeignKey("schedules.schedule_id"),
        nullable=False,
    )
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(String(20), nullable=False)

    schedule = relationship(
        "Schedule",
        back_populates="time_slots",
    )