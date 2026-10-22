from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class PetOwner(Base):
    __tablename__ = "pet_owners"

    __table_args__ = (
        CheckConstraint(
            "user_id IS NOT NULL OR "
            "(contact_name IS NOT NULL AND contact_phone IS NOT NULL)",
            name="chk_pet_owner_identity",
        ),
    )

    pet_owner_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True,
        unique=True,
    )

    contact_name = Column(String(150), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    contact_email = Column(String(255), nullable=True)

    default_address = Column(String(255), nullable=True)

    user = relationship(
        "User",
        back_populates="pet_owner",
    )

    pets = relationship(
        "Pet",
        back_populates="owner",
    )