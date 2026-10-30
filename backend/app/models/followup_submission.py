from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
    select,
)
from sqlalchemy.orm import relationship, column_property

from app.database import Base
from app.models.followup_review_decision import FollowupReviewDecision


class FollowupSubmission(Base):
    __tablename__ = "followup_submissions"

    __table_args__ = (
        CheckConstraint(
            "review_status IN "
            "('submitted', 'reviewed', 'more_requested')",
            name="chk_submission_review_status",
        ),
    )

    submission_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    followup_care_id = Column(
        Integer,
        ForeignKey("followup_care.followup_care_id"),
        nullable=False,
    )

    pet_owner_id = Column(
        Integer,
        ForeignKey("pet_owners.pet_owner_id"),
        nullable=False,
    )

    owner_comment = Column(Text, nullable=True)

    submitted_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    review_status = Column(
        String(30),
        nullable=False,
        default="submitted",
        server_default=text("'submitted'"),
    )

    veterinarian_comment = Column(Text, nullable=True)

    reviewed_by_veterinarian_id = Column(
        Integer,
        ForeignKey("veterinarians.veterinarian_id"),
        nullable=True,
    )

    reviewed_at = Column(DateTime, nullable=True)

    decision_outcome = column_property(
    select(FollowupReviewDecision.outcome)
    .where(
        FollowupReviewDecision.submission_id == submission_id
    )
    .order_by(FollowupReviewDecision.decision_id.desc())
    .limit(1)
    .correlate_except(FollowupReviewDecision)
    .scalar_subquery()
)

    followup = relationship(
        "FollowupCare",
        back_populates="submissions",
    )

    owner = relationship("PetOwner")

    reviewer = relationship(
        "Veterinarian",
        foreign_keys=[reviewed_by_veterinarian_id],
    )

    images = relationship(
        "FollowupImage",
        back_populates="submission",
    )