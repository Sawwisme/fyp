from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class EmergencyAppointment(Base):
    __tablename__ = "emergency_appointments"

    emergency_appointment_id = Column(
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
    urgency_level = Column(String(20), nullable=False)
    emergency_reason = Column(Text, nullable=False)
    approval_status = Column(String(20), nullable=False)
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

    appointment = relationship(
        "Appointment",
        back_populates="emergency_request",
    )
    assigned_veterinarian = relationship("Veterinarian")
    approving_administrator = relationship("ClinicAdministrator")