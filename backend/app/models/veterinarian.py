from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Veterinarian(Base):
    __tablename__ = "veterinarians"

    veterinarian_id = Column(
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
    registration_number = Column(
        String(50),
        nullable=False,
        unique=True,
    )
    qualification = Column(String(150), nullable=True)
    specialization = Column(String(100), nullable=True)
    years_experience = Column(Integer, nullable=True)
    approval_status = Column(String(20), nullable=False)
    clinic_name = Column(String(150), nullable=True)

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.clinic_id"),
        nullable=True,
    )

    clinic = relationship(
        "Clinic",
        back_populates="veterinarians",
    )

    user = relationship("User", back_populates="veterinarian")
    
    schedules = relationship(
        "Schedule",
        back_populates="veterinarian",
    )