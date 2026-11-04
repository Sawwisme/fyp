from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Refund(Base):
    __tablename__ = "refunds"

    __table_args__ = (
        UniqueConstraint(
            "gateway_refund_id",
            name="uq_refund_gateway_reference",
        ),
        UniqueConstraint(
            "gateway_idempotency_key",
            name="uq_refund_gateway_idempotency",
        ),
        Index(
            "ix_refund_transaction_status",
            "transaction_id",
            "status",
        ),
        Index(
            "ix_refund_status_requested",
            "status",
            "requested_at",
        ),
    )

    refund_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

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
        ForeignKey(
            "clinic_administrators.clinic_administrator_id"
        ),
        nullable=True,
    )

    refund_amount = Column(
        Numeric(10, 2),
        nullable=False,
    )

    reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False)

    version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    gateway_refund_id = Column(
        String(100),
        nullable=True,
    )

    gateway_idempotency_key = Column(
        String(36),
        nullable=True,
    )

    gateway_requested_at = Column(
        DateTime,
        nullable=True,
    )

    failure_reason = Column(Text, nullable=True)

    requested_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    processed_at = Column(
        DateTime,
        nullable=True,
    )

    stock_reviewed_at = Column(
        DateTime,
        nullable=True,
    )

    stock_reviewed_by = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True,
    )

    stock_review_notes = Column(
        Text,
        nullable=True,
    )

    stock_return_items = Column(
        JSON,
        nullable=True,
    )

    transaction = relationship(
        "Transaction",
        back_populates="refunds",
    )

    requester = relationship(
        "User",
        foreign_keys=[requested_by],
    )

    approving_administrator = relationship(
        "ClinicAdministrator"
    )