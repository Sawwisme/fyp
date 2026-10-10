from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    appointment_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    pet_owner_id = Column(
        Integer,
        ForeignKey("pet_owners.pet_owner_id"),
        nullable=False,
    )
    pet_id = Column(
        Integer,
        ForeignKey("pets.pet_id"),
        nullable=False,
    )
    veterinarian_id = Column(
        Integer,
        ForeignKey("veterinarians.veterinarian_id"),
        nullable=True,
    )
    time_slot_id = Column(
        Integer,
        ForeignKey("time_slots.time_slot_id"),
        nullable=False,
    )
    appointment_type = Column(String(30), nullable=False)
    appointment_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    owner = relationship("PetOwner")
    pet = relationship("Pet")
    veterinarian = relationship("Veterinarian")
    time_slot = relationship("TimeSlot")

    emergency_request = relationship(
        "EmergencyAppointment",
        back_populates="appointment",
        uselist=False,
    )