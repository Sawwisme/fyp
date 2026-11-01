from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


def notification_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "event_key",
            name="uq_notification_user_event",
        ),
        Index(
            "ix_notification_user_created",
            "user_id",
            "created_at",
            "notification_id",
        ),
        Index(
            "ix_notification_user_read",
            "user_id",
            "read_at",
        ),
    )

    notification_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    event_key = Column(String(190), nullable=False)
    notification_type = Column(String(50), nullable=False)

    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)

    resource_type = Column(String(50), nullable=False)
    resource_id = Column(Integer, nullable=False)

    created_at = Column(
        DateTime,
        nullable=False,
        default=notification_utc_now,
    )
    read_at = Column(DateTime, nullable=True)