from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import relationship

from app.database import Base


class ClinicWorkingHour(Base):
    __tablename__ = "clinic_working_hours"

    __table_args__ = (
        UniqueConstraint(
            "clinic_id",
            "weekday",
            "start_time",
            name="uq_clinic_weekday_start",
        ),
    )

    clinic_working_hour_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.clinic_id"),
        nullable=False,
    )

    weekday = Column(
        Integer().with_variant(TINYINT(), "mysql"),
        nullable=False,
    )

    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    clinic = relationship(
        "Clinic",
        back_populates="working_hours",
    )