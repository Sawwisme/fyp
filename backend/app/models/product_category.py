from sqlalchemy import Column, DateTime, Integer, String, Text, text
from sqlalchemy.orm import relationship

from app.database import Base


class ProductCategory(Base):
    __tablename__ = "product_categories"

    category_id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    products = relationship("Product", back_populates="category")