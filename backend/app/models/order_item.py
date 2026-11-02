from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    order_id = Column(
        Integer,
        ForeignKey("orders.order_id"),
        nullable=False,
    )
    product_id = Column(
        Integer,
        ForeignKey("products.product_id"),
        nullable=False,
    )
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)
    product_name = Column(String(150), nullable=True)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")