from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import relationship

from app.database import Base


class DentalImage(Base):
    __tablename__ = "dental_images"

    dental_image_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    pet_id = Column(
        Integer,
        ForeignKey("pets.pet_id"),
        nullable=False,
    )
    uploaded_by = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
    )
    image_url = Column(String(500), nullable=False)
    uploaded_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    pet = relationship("Pet")
    uploader = relationship("User")
    analyses = relationship(
        "AIAnalysisResult",
        back_populates="dental_image",
    )