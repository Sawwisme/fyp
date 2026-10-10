from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Pet(Base):
    __tablename__ = "pets"

    pet_id = Column(Integer, primary_key=True, autoincrement=True)
    pet_owner_id = Column(
        Integer,
        ForeignKey("pet_owners.pet_owner_id"),
        nullable=False,
    )
    pet_name = Column(String(100), nullable=False)
    species = Column(String(30), nullable=False)
    breed = Column(String(100), nullable=True)
    gender = Column(String(20), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    weight = Column(Numeric(5, 2), nullable=True)
    colour = Column(String(50), nullable=True)
    existing_dental_condition = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    owner = relationship("PetOwner", back_populates="pets")