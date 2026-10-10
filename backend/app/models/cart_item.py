from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class CartItem(Base):
    __tablename__ = "cart_items"

    __table_args__ = (
        UniqueConstraint(
            "cart_id",
            "product_id",
            name="uq_cart_product",
        ),
    )

    cart_item_id = Column(Integer, primary_key=True, autoincrement=True)
    cart_id = Column(
        Integer,
        ForeignKey("carts.cart_id"),
        nullable=False,
    )
    product_id = Column(
        Integer,
        ForeignKey("products.product_id"),
        nullable=False,
    )
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")