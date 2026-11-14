from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ConsultationProductRecommendation(Base):
    __tablename__ = "consultation_product_recommendations"

    __table_args__ = (
        UniqueConstraint(
            "consultation_id",
            "product_id",
            name="uq_consultation_recommended_product",
        ),
    )

    recommendation_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    consultation_id = Column(
        Integer,
        ForeignKey("consultations.consultation_id"),
        nullable=False,
    )

    product_id = Column(
        Integer,
        ForeignKey("products.product_id"),
        nullable=False,
    )

    # Preserve what the vet selected if the catalogue name changes.
    product_name_snapshot = Column(
        String(150),
        nullable=False,
    )

    instructions = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    consultation = relationship("Consultation")
    product = relationship("Product")