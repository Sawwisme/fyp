from sqlalchemy import Column, ForeignKey, Integer, String, text
from sqlalchemy.orm import relationship

from app.database import Base


class ClinicAdministrator(Base):
    __tablename__ = "clinic_administrators"

    clinic_administrator_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
        unique=True,
    )
    clinic_name = Column(String(150), nullable=False)

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.clinic_id"),
        nullable=True,
    )

    membership_status = Column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )

    clinic = relationship(
        "Clinic",
        back_populates="administrators",
    )

    user = relationship(
        "User",
        back_populates="clinic_administrator",
    )