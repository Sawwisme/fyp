from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class AIAssessmentReview(Base):
    __tablename__ = "ai_assessment_reviews"

    __table_args__ = (
        UniqueConstraint(
            "analysis_id",
            "clinic_id",
            name="uq_ai_review_analysis_clinic",
        ),
        CheckConstraint(
            "status IN ('pending', 'reviewed', 'cancelled')",
            name="chk_ai_review_status",
        ),
        CheckConstraint(
            "reviewed_severity IS NULL OR reviewed_severity IN "
            "('none', 'mild', 'moderate', 'severe', 'unable_to_assess')",
            name="chk_ai_review_severity",
        ),
        CheckConstraint(
            "recommended_action IS NULL OR recommended_action IN "
            "('routine_booking', 'prompt_clinic_assessment', "
            "'home_care', 'unable_to_assess')",
            name="chk_ai_review_action",
        ),
        CheckConstraint(
            "("
            "status = 'reviewed' "
            "AND reviewed_by_veterinarian_id IS NOT NULL "
            "AND reviewed_severity IS NOT NULL "
            "AND recommended_action IS NOT NULL "
            "AND feedback IS NOT NULL "
            "AND CHAR_LENGTH(TRIM(feedback)) > 0 "
            "AND reviewed_at IS NOT NULL"
            ") OR ("
            "status IN ('pending', 'cancelled') "
            "AND reviewed_by_veterinarian_id IS NULL "
            "AND reviewed_severity IS NULL "
            "AND recommended_action IS NULL "
            "AND feedback IS NULL "
            "AND reviewed_at IS NULL"
            ")",
            name="chk_ai_review_completion",
        ),
        Index(
            "ix_ai_review_clinic_status",
            "clinic_id",
            "status",
            "requested_at",
        ),
        Index(
            "ix_ai_review_requester",
            "requested_by_user_id",
            "requested_at",
        ),
    )

    review_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    analysis_id = Column(
        Integer,
        ForeignKey("ai_analysis_results.analysis_id"),
        nullable=False,
    )
    clinic_id = Column(
        Integer,
        ForeignKey("clinics.clinic_id"),
        nullable=False,
    )
    requested_by_user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    status = Column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    owner_message = Column(Text, nullable=True)

    reviewed_by_veterinarian_id = Column(
        Integer,
        ForeignKey("veterinarians.veterinarian_id"),
        nullable=True,
    )
    reviewed_severity = Column(String(30), nullable=True)
    recommended_action = Column(String(30), nullable=True)
    feedback = Column(Text, nullable=True)

    requested_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    reviewed_at = Column(DateTime, nullable=True)

    analysis = relationship("AIAnalysisResult")
    clinic = relationship("Clinic")
    requested_by = relationship("User")
    reviewed_by = relationship("Veterinarian")