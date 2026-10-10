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


class AIAnalysisResult(Base):
    __tablename__ = "ai_analysis_results"

    analysis_id = Column(Integer, primary_key=True, autoincrement=True)
    dental_image_id = Column(
        Integer,
        ForeignKey("dental_images.dental_image_id"),
        nullable=False,
    )
    heatmap_url = Column(String(500), nullable=True)
    segmentation_url = Column(String(500), nullable=True)
    analysis_date = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    model_version = Column(String(100), nullable=True)
    veterinarian_override = Column(String(30), nullable=True)
    override_notes = Column(Text, nullable=True)

    dental_image = relationship(
        "DentalImage",
        back_populates="analyses",
    )
    predictions = relationship(
        "AIAnalysisPrediction",
        back_populates="analysis",
    )