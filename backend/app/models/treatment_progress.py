from sqlalchemy.orm import relationship

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)

from app.database import Base


class TreatmentProgress(Base):
    __tablename__ = "treatment_progress"

    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('planned', 'in_progress', 'completed', 'cancelled')",
            name="chk_treatment_progress_status",
        ),
    )

    treatment_id = Column(
        Integer,
        ForeignKey("treatments.treatment_id"),
        primary_key=True,
        autoincrement=False,
    )

    status = Column(
        String(20),
        nullable=False,
        default="planned",
        server_default=text("'planned'"),
    )

    started_at = Column(DateTime, nullable=True)
    start_consultation_id = Column(
        Integer,
        ForeignKey("consultations.consultation_id"),
        nullable=True,
    )

    start_notes = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    completion_consultation_id = Column(
        Integer,
        ForeignKey("consultations.consultation_id"),
        nullable=True,
    )

    cancellation_reason = Column(Text, nullable=True)

    updated_by_user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True,
    )

    updated_at = Column(DateTime, nullable=True)

    version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    treatment = relationship(
        "Treatment",
        back_populates="progress_record",
    )