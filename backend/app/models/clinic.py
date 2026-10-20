from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    text,
    BigInteger,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Clinic(Base):
    __tablename__ = "clinics"

    __table_args__ = (
        UniqueConstraint(
            "osm_type",
            "osm_id",
            name="uq_clinic_osm_identity",
        ),
    )
    clinic_id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_code = Column(String(50), nullable=False, unique=True)
    clinic_name = Column(String(150), nullable=False)
    osm_type = Column(String(10), nullable=True)
    osm_id = Column(BigInteger, nullable=True)

    address = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)

    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)

    status = Column(
        String(20),
        nullable=False,
        server_default=text("'active'"),
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated_at = Column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    administrators = relationship(
        "ClinicAdministrator",
        back_populates="clinic",
    )

    veterinarians = relationship(
        "Veterinarian",
        back_populates="clinic",
    )

    working_hours = relationship(
        "ClinicWorkingHour",
        back_populates="clinic",
        order_by="ClinicWorkingHour.weekday, ClinicWorkingHour.start_time",
    )