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


class StripeCheckoutSession(Base):
    __tablename__ = "stripe_checkout_sessions"

    __table_args__ = (
        UniqueConstraint(
            "order_id",
            name="uq_stripe_checkout_order",
        ),
        UniqueConstraint(
            "payment_id",
            name="uq_stripe_checkout_payment",
        ),
        UniqueConstraint(
            "stripe_session_id",
            name="uq_stripe_checkout_session",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_stripe_checkout_idempotency",
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="chk_stripe_checkout_amount",
        ),
        Index(
            "ix_stripe_checkout_status_expiry",
            "session_status",
            "expires_at",
        ),
    )

    checkout_session_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    order_id = Column(
        Integer,
        ForeignKey("orders.order_id"),
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

    # Preserve the exact Stripe request for safe retries.
    request_payload = Column(JSON, nullable=False)

    session_status = Column(
        String(20),
        nullable=False,
        default="creating",
        server_default=text("'creating'"),
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    expires_at = Column(DateTime, nullable=False)

    order = relationship("Order")
    payment = relationship("Payment")