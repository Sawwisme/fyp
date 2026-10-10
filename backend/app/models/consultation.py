from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Consultation(Base):
    __tablename__ = "consultations"

    consultation_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.appointment_id"),
        nullable=False,
        unique=True,
    )
    pet_id = Column(
        Integer,
        ForeignKey("pets.pet_id"),
        nullable=False,
    )
    veterinarian_id = Column(
        Integer,
        ForeignKey("veterinarians.veterinarian_id"),
        nullable=False,
    )
    consultation_date = Column(DateTime, nullable=False)
    consultation_information = Column(Text, nullable=True)
    diagnosis = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    appointment = relationship("Appointment")
    pet = relationship("Pet")
    veterinarian = relationship("Veterinarian")

    dental_records = relationship(
        "DentalRecord",
        back_populates="consultation",
    )
    prescriptions = relationship(
        "Prescription",
        back_populates="consultation",
    )
    treatments = relationship(
        "Treatment",
        back_populates="consultation",
    )
    followups = relationship(
        "FollowupCare",
        back_populates="consultation",
    )