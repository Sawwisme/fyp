from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
    CheckConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    __table_args__ = (
        CheckConstraint(
            "planned_treatment_id IS NULL "
            "OR followup_care_id IS NULL",
            name="chk_appointment_return_visit",
        ),
    )

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
    appointment_source = Column(String(20), nullable=True)

    planned_treatment_id = Column(
        Integer,
        ForeignKey("treatment_progress.treatment_id"),
        nullable=True,
    )

    followup_care_id = Column(
        Integer,
        ForeignKey("followup_care.followup_care_id"),
        nullable=True,
    )

    created_by_user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True,
    )
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

    consultation = relationship(
        "Consultation",
        back_populates="appointment",
        uselist=False,
    )

    treatment_plan = relationship(
        "TreatmentProgress",
        foreign_keys=[planned_treatment_id],
    )

    followup_task = relationship(
        "FollowupCare",
        foreign_keys=[followup_care_id],
    )
