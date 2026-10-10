from sqlalchemy import Column, DateTime, Integer, String, text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=True)

    role = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False)


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

    pet_owner = relationship(
        "PetOwner",
        back_populates="user",
        uselist=False,
    )

    veterinarian = relationship(
        "Veterinarian",
        back_populates="user",
        uselist=False,
    )
    
    clinic_administrator = relationship(
        "ClinicAdministrator",
        back_populates="user",
        uselist=False,
    )
