from sqlalchemy import Column, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Prescription(Base):
    __tablename__ = "prescriptions"

    prescription_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    consultation_id = Column(
        Integer,
        ForeignKey("consultations.consultation_id"),
        nullable=False,
    )
    veterinarian_id = Column(
        Integer,
        ForeignKey("veterinarians.veterinarian_id"),
        nullable=False,
    )
    medication_name = Column(String(150), nullable=False)
    dosage = Column(String(100), nullable=False)
    frequency = Column(String(100), nullable=True)
    duration = Column(String(100), nullable=True)
    instructions = Column(Text, nullable=True)
    prescription_date = Column(Date, nullable=False)

    consultation = relationship(
        "Consultation",
        back_populates="prescriptions",
    )
    veterinarian = relationship("Veterinarian")