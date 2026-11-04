from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    __table_args__ = (
        UniqueConstraint(
            "order_id",
            "resulting_version",
            name="uq_order_history_version",
        ),
        Index(
            "ix_order_history_order_created",
            "order_id",
            "created_at",
            "history_id",
        ),
    )

    history_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    order_id = Column(
        Integer,
        ForeignKey("orders.order_id"),
        nullable=False,
    )
    changed_by_user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True,
    )

    previous_status = Column(String(30), nullable=False)
    new_status = Column(String(30), nullable=False)
    resulting_version = Column(Integer, nullable=False)
    notes = Column(String(500), nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )