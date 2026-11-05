from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class BillingStripeSession(Base):
    __tablename__ = "billing_stripe_sessions"

    __table_args__ = (
        UniqueConstraint(
            "payment_id",
            name="uq_billing_stripe_payment",
        ),
        UniqueConstraint(
            "stripe_session_id",
            name="uq_billing_stripe_session",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_billing_stripe_idempotency",
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="chk_billing_stripe_amount",
        ),
        Index(
            "ix_billing_stripe_bill_status",
            "consultation_bill_id",
            "session_status",
            "billing_checkout_id",
        ),
        Index(
            "ix_billing_stripe_status_created",
            "session_status",
            "created_at",
        ),
    )

    billing_checkout_id = Column(
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

    stripe_session_id = Column(
        String(255),
        nullable=True,
    )

    checkout_url = Column(Text, nullable=True)

    idempotency_key = Column(
        String(36),
        nullable=False,
    )

    amount_cents = Column(
        BigInteger,
        nullable=False,
    )

    currency = Column(
        String(3),
        nullable=False,
        default="myr",
        server_default=text("'myr'"),
    )

    request_payload = Column(JSON, nullable=False)

    session_status = Column(
        String(30),
        nullable=False,
        default="creating",
        server_default=text("'creating'"),
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(
            tzinfo=None
        ),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    expires_at = Column(
        DateTime,
        nullable=True,
    )

    bill = relationship("ConsultationBill")
    payment = relationship("Payment")