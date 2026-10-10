from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class FollowupImage(Base):
    __tablename__ = "followup_images"

    followup_care_image_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    followup_care_id = Column(
        Integer,
        ForeignKey("followup_care.followup_care_id"),
        nullable=False,
    )
    image_url = Column(String(255), nullable=False)
    uploaded_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    followup = relationship(
        "FollowupCare",
        back_populates="images",
    )