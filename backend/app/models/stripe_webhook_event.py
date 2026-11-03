from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, String

from app.database import Base


class StripeWebhookEvent(Base):
    __tablename__ = "stripe_webhook_events"

    __table_args__ = (
        Index(
            "ix_stripe_events_pending",
            "processing_status",
            "received_at",
        ),
    )

    event_id = Column(String(255), primary_key=True)
    event_type = Column(String(100), nullable=False)
    session_id = Column(String(255), nullable=False)

    processing_status = Column(
        String(20),
        nullable=False,
        default="pending",
    )

    received_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    processed_at = Column(DateTime, nullable=True)