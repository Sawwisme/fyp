from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class EmergencyAppointment(Base):
    __tablename__ = "emergency_appointments"

    emergency_appointment_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # No appointment exists until the clinic accepts the request.
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.appointment_id"),
        nullable=True,
        unique=True,
    )

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.clinic_id"),
        nullable=False,
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

    urgency_level = Column(
        String(20),
        nullable=False,
        default="unassessed",
    )

    emergency_reason = Column(Text, nullable=False)

    approval_status = Column(
        String(20),
        nullable=False,
        default="pending",
    )

    assigned_veterinarian_id = Column(
        Integer,
        ForeignKey("veterinarians.veterinarian_id"),
        nullable=True,
    )

    approved_by = Column(
        Integer,
        ForeignKey("clinic_administrators.clinic_administrator_id"),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    appointment = relationship(
        "Appointment",
        back_populates="emergency_request",
    )

    clinic = relationship("Clinic")
    owner = relationship("PetOwner")
    pet = relationship("Pet")

    assigned_veterinarian = relationship("Veterinarian")
    approving_administrator = relationship("ClinicAdministrator")