from sqlalchemy import (
    Column,
    Computed,
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


class ProductCategory(Base):
    __tablename__ = "product_categories"

    __table_args__ = (
        UniqueConstraint(
            "category_scope",
            "category_name",
            name="uq_product_category_scope_name",
        ),
    )

    category_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.clinic_id"),
        nullable=True,
    )

    category_scope = Column(
        Integer,
        Computed(
            "COALESCE(clinic_id, 0)",
            persisted=True,
        ),
    )

    category_name = Column(
        String(100),
        nullable=False,
    )

    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    products = relationship(
        "Product",
        back_populates="category",
    )

    clinic = relationship("Clinic")