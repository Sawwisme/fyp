from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class FollowupCare(Base):
    __tablename__ = "followup_care"

    followup_care_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    consultation_id = Column(
        Integer,
        ForeignKey("consultations.consultation_id"),
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
        nullable=False,
    )
    followup_date = Column(DateTime, nullable=False)
    assessment_information = Column(Text, nullable=True)
    status = Column(String(20), nullable=False)
    notes = Column(Text, nullable=True)

    consultation = relationship(
        "Consultation",
        back_populates="followups",
    )
    pet = relationship("Pet")
    veterinarian = relationship("Veterinarian")
    images = relationship(
        "FollowupImage",
        back_populates="followup",
    )