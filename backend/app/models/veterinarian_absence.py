from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)

from app.database import Base


class VeterinarianAbsence(Base):
    __tablename__ = "veterinarian_absences"

    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="chk_absence_times",
        ),
        CheckConstraint(
            "status IN ('active', 'cancelled')",
            name="chk_absence_status",
        ),
        Index(
            "ix_absence_vet_date",
            "veterinarian_id",
            "absence_date",
            "status",
        ),
    )

    absence_id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_id = Column(
        Integer, ForeignKey("clinics.clinic_id"), nullable=False
    )
    veterinarian_id = Column(
        Integer,
        ForeignKey("veterinarians.veterinarian_id"),
        nullable=False,
    )
    absence_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )
    created_by_user_id = Column(
        Integer, ForeignKey("users.user_id"), nullable=False
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    cancelled_at = Column(DateTime, nullable=True)


class AbsenceAffectedAppointment(Base):
    __tablename__ = "absence_affected_appointments"

    __table_args__ = (
        UniqueConstraint(
            "absence_id",
            "appointment_id",
            name="uq_absence_appointment",
        ),
        CheckConstraint(
            "resolution_status IN "
            "('pending', 'rescheduled', 'reassigned', "
            "'cancelled', 'no_change')",
            name="chk_absence_resolution",
        ),
        Index(
            "ix_affected_resolution",
            "absence_id",
            "resolution_status",
        ),
    )

    affected_id = Column(Integer, primary_key=True, autoincrement=True)
    absence_id = Column(
        Integer,
        ForeignKey("veterinarian_absences.absence_id"),
        nullable=False,
    )
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.appointment_id"),
        nullable=False,
    )
    original_time_slot_id = Column(
        Integer,
        ForeignKey("time_slots.time_slot_id"),
        nullable=False,
    )
    resolution_status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    resolution_note = Column(Text, nullable=True)
    owner_agreement_note = Column(Text, nullable=True)
    resolved_by_user_id = Column(
        Integer, ForeignKey("users.user_id"), nullable=True
    )
    resolved_at = Column(DateTime, nullable=True)