from sqlalchemy import Column, Date, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base


class DentalRecord(Base):
    __tablename__ = "dental_records"

    dental_record_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
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
    consultation_id = Column(
        Integer,
        ForeignKey("consultations.consultation_id"),
        nullable=True,
    )
    record_date = Column(Date, nullable=False)
    dental_condition = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    pet = relationship("Pet")
    veterinarian = relationship("Veterinarian")
    consultation = relationship(
        "Consultation",
        back_populates="dental_records",
    )