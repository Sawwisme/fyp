from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Refund(Base):
    __tablename__ = "refunds"

    refund_id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(
        Integer,
        ForeignKey("transactions.transaction_id"),
        nullable=False,
    )
    requested_by = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
    )
    approved_by = Column(
        Integer,
        ForeignKey("clinic_administrators.clinic_administrator_id"),
        nullable=True,
    )
    refund_amount = Column(Numeric(10, 2), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False)
    requested_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    processed_at = Column(DateTime, nullable=True)

    transaction = relationship("Transaction", back_populates="refunds")
    requester = relationship("User")
    approving_administrator = relationship("ClinicAdministrator")