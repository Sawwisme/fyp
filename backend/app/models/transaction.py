from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True,
    )
    order_id = Column(
        Integer,
        ForeignKey("orders.order_id"),
        nullable=True,
    )
    payment_id = Column(
        Integer,
        ForeignKey("payments.payment_id"),
        nullable=True,
    )
    transaction_type = Column(String(30), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    transaction_status = Column(String(20), nullable=False)
    transaction_date = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user = relationship("User")
    order = relationship("Order")
    payment = relationship("Payment", back_populates="transactions")
    refunds = relationship("Refund", back_populates="transaction")