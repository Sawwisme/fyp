from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    text,
)

from app.database import Base


class ClinicOwnerLink(Base):
    __tablename__ = "clinic_owner_links"

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.clinic_id"),
        primary_key=True,
    )

    pet_owner_id = Column(
        Integer,
        ForeignKey("pet_owners.pet_owner_id"),
        primary_key=True,
    )

    created_by_user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )