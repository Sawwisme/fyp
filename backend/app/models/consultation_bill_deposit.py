from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ConsultationBillDeposit(Base):
    __tablename__ = "consultation_bill_deposits"

    __table_args__ = (
        UniqueConstraint(
            "consultation_bill_id",
            name="uq_bill_deposit_bill",
        ),
        UniqueConstraint(
            "payment_id",
            name="uq_bill_deposit_payment",
        ),
        UniqueConstraint(
            "excess_refund_id",
            name="uq_bill_deposit_excess_refund",
        ),
        CheckConstraint(
            "deposit_amount > 0 "
            "AND applied_amount >= 0 "
            "AND excess_refund_amount >= 0 "
            "AND deposit_amount = "
            "applied_amount + excess_refund_amount",
            name="chk_bill_deposit_amounts",
        ),
    )

    consultation_bill_deposit_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    consultation_bill_id = Column(
        Integer,
        ForeignKey("consultation_bills.consultation_bill_id"),
        nullable=False,
    )

    payment_id = Column(
        Integer,
        ForeignKey("payments.payment_id"),
        nullable=False,
    )

    excess_refund_id = Column(
        Integer,
        ForeignKey("refunds.refund_id"),
        nullable=True,
    )

    deposit_amount = Column(
        Numeric(10, 2),
        nullable=False,
    )

    applied_amount = Column(
        Numeric(10, 2),
        nullable=False,
    )

    excess_refund_amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default=text("0.00"),
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(
            tzinfo=None
        ),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    bill = relationship(
        "ConsultationBill",
        back_populates="deposit_application",
    )

    payment = relationship("Payment")
    excess_refund = relationship("Refund")