from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(
        Integer,
        ForeignKey("orders.order_id"),
        nullable=True,
    )
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.appointment_id"),
        nullable=True,
    )
    payment_method = Column(String(30), nullable=False)
    payment_status = Column(String(20), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    payment_date = Column(DateTime, nullable=True)
    gateway_reference = Column(String(100), nullable=True, unique=True)
    receipt_number = Column(String(50), nullable=True, unique=True)

    order = relationship("Order")
    appointment = relationship("Appointment")
    transactions = relationship(
        "Transaction",
        back_populates="payment",
    )