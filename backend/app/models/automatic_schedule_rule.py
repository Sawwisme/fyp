from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)

from app.database import Base


class AutomaticScheduleRule(Base):
    __tablename__ = "automatic_schedule_rules"

    automatic_schedule_rule_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    veterinarian_id = Column(
        Integer,
        ForeignKey("veterinarians.veterinarian_id"),
        nullable=False,
        unique=True,
    )

    enabled = Column(
        Boolean,
        nullable=False,
        server_default=text("0"),
    )

    slot_minutes = Column(
        Integer,
        nullable=False,
        server_default=text("30"),
    )

    days_ahead = Column(
        Integer,
        nullable=False,
        server_default=text("30"),
    )

    last_run_at = Column(DateTime, nullable=True)
    last_error = Column(String(1000), nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )