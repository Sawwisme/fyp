from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)

from app.database import Base


class FollowupReviewDecision(Base):
    __tablename__ = "followup_review_decisions"

    __table_args__ = (
        CheckConstraint(
            "outcome IN "
            "('complete', 'request_update', 'in_clinic')",
            name="chk_followup_decision_outcome",
        ),
        Index(
            "ix_followup_decision_submission",
            "submission_id",
            "decision_id",
        ),
    )

    decision_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    submission_id = Column(
        Integer,
        ForeignKey("followup_submissions.submission_id"),
        nullable=False,
    )

    correction_reason = Column(Text, nullable=True)

    veterinarian_id = Column(
        Integer,
        ForeignKey("veterinarians.veterinarian_id"),
        nullable=False,
    )

    outcome = Column(String(30), nullable=False)
    veterinarian_comment = Column(Text, nullable=False)

    decided_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    previous_review_status = Column(String(30), nullable=False)
    previous_comment = Column(Text, nullable=True)
    previous_reviewed_at = Column(DateTime, nullable=True)

    previous_reviewer_id = Column(
        Integer,
        ForeignKey("veterinarians.veterinarian_id"),
        nullable=True,
    )