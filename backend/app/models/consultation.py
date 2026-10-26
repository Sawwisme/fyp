from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
    Boolean,
    Date,
)
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

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.clinic_id"),
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

    ai_analysis_id = Column(
        Integer,
        ForeignKey("ai_analysis_results.analysis_id"),
        nullable=True,
    )

    ai_analysis = relationship("AIAnalysisResult")

    consultation_date = Column(DateTime, nullable=False)\

    followup_required = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    followup_recommended_date = Column(
        Date,
        nullable=True,
    )

    followup_reason = Column(Text, nullable=True)
    followup_instructions = Column(Text, nullable=True)

    # Presenting complaint and consultation history.
    consultation_information = Column(Text, nullable=True)
    examination_findings = Column(Text, nullable=True)
    diagnosis = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    status = Column(
        String(20),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
    )

    completed_at = Column(DateTime, nullable=True)

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    # Used to detect conflicting saves from multiple tabs.
    version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    appointment = relationship(
    "Appointment",
    back_populates="consultation",
    )
    clinic = relationship("Clinic")
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