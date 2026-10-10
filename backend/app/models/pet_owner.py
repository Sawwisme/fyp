from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class PetOwner(Base):
    __tablename__ = "pet_owners"

    pet_owner_id = Column(
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
    default_address = Column(String(255), nullable=True)

    user = relationship("User", back_populates="pet_owner")

    pets = relationship("Pet", back_populates="owner")