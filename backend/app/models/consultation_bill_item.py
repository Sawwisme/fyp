from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ConsultationBillItem(Base):
    __tablename__ = "consultation_bill_items"

    __table_args__ = (
        CheckConstraint(
            "item_type IN "
            "('consultation', 'procedure', 'medication', 'other')",
            name="chk_consultation_bill_item_type",
        ),
        CheckConstraint(
            "quantity BETWEEN 1 AND 999 "
            "AND unit_price >= 0 "
            "AND subtotal >= 0 "
            "AND subtotal = quantity * unit_price",
            name="chk_consultation_bill_item_amount",
        ),
        Index(
            "ix_consultation_bill_item_bill",
            "consultation_bill_id",
            "consultation_bill_item_id",
        ),
    )

    consultation_bill_item_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    consultation_bill_id = Column(
        Integer,
        ForeignKey("consultation_bills.consultation_bill_id"),
        nullable=False,
    )

    item_type = Column(String(30), nullable=False)
    description = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)

    bill = relationship(
        "ConsultationBill",
        back_populates="items",
    )