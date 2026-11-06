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


class BookingStripeSession(Base):
    __tablename__ = "booking_stripe_sessions"

    __table_args__ = (
        UniqueConstraint(
            "payment_id",
            name="uq_booking_stripe_payment",
        ),
        UniqueConstraint(
            "stripe_session_id",
            name="uq_booking_stripe_session",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_booking_stripe_idempotency",
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="chk_booking_stripe_amount",
        ),
        Index(
            "ix_booking_stripe_appointment_status",
            "appointment_id",
            "session_status",
            "booking_checkout_id",
        ),
        Index(
            "ix_booking_stripe_status_created",
            "session_status",
            "created_at",
        ),
    )

    booking_checkout_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    appointment_id = Column(
        Integer,
        ForeignKey("appointments.appointment_id"),
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

    request_payload = Column(
        JSON,
        nullable=False,
    )

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

    appointment = relationship("Appointment")
    payment = relationship("Payment")