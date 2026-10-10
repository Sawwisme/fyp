from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class AIAnalysisPrediction(Base):
    __tablename__ = "ai_analysis_predictions"

    __table_args__ = (
        UniqueConstraint(
            "analysis_id",
            "condition_name",
            name="uq_analysis_condition",
        ),
    )

    prediction_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    analysis_id = Column(
        Integer,
        ForeignKey("ai_analysis_results.analysis_id"),
        nullable=False,
    )
    condition_name = Column(String(50), nullable=False)
    confidence_score = Column(Numeric(6, 5), nullable=False)
    predicted_positive = Column(Boolean, nullable=False)
    supported = Column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
    )

    analysis = relationship(
        "AIAnalysisResult",
        back_populates="predictions",
    )