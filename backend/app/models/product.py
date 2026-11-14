from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    JSON,
    text,
    Index,
    CheckConstraint,
)

from sqlalchemy.orm import relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        CheckConstraint(
            "target_species IN ('unknown', 'cat', 'dog', 'both')",
            name="chk_product_target_species",
        ),
        CheckConstraint(
            "minimum_age_months IS NULL OR "
            "minimum_age_months BETWEEN 0 AND 600",
            name="chk_product_minimum_age",
        ),
        Index(
            "ix_product_clinic_status",
            "clinic_id",
            "status",
            "product_id",
        ),
    )

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_id = Column(
        Integer,
        ForeignKey("clinics.clinic_id"),
        nullable=True,
    )
    category_id = Column(
        Integer,
        ForeignKey("product_categories.category_id"),
        nullable=False,
    )
    product_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    target_species = Column(
        String(20),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
    )
    minimum_age_months = Column(Integer, nullable=True)
    suitability_notes = Column(Text, nullable=True)
    recommendation_tags = Column(
        JSON,
        nullable=True,
    )

    recommendation_enabled = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    price = Column(Numeric(10, 2), nullable=False)
    stock_quantity = Column(Integer, nullable=False)
    image_url = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    category = relationship("ProductCategory", back_populates="products")
    clinic = relationship("Clinic")