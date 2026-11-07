from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    text,
)

from app.database import Base


class DentalAssessmentJob(Base):
    __tablename__ = "dental_assessment_jobs"

    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('queued', 'running', 'completed', 'rejected', 'failed')",
            name="chk_assessment_job_status",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="chk_assessment_job_attempts",
        ),
        Index(
            "ix_assessment_job_queue",
            "status",
            "created_at",
        ),
        Index(
            "ix_assessment_job_lease",
            "status",
            "locked_until",
        ),
    )

    assessment_job_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    dental_image_id = Column(
        Integer,
        ForeignKey("dental_images.dental_image_id"),
        nullable=False,
        unique=True,
    )

    analysis_id = Column(
        Integer,
        ForeignKey("ai_analysis_results.analysis_id"),
        nullable=True,
        unique=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )

    attempts = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    claim_token = Column(String(36), nullable=True)
    locked_until = Column(DateTime, nullable=True)

    result_summary = Column(JSON, nullable=True)
    error_message = Column(String(500), nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)