from sqlalchemy import Column, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Treatment(Base):
    __tablename__ = "treatments"

    treatment_id = Column(Integer, primary_key=True, autoincrement=True)
    consultation_id = Column(
        Integer,
        ForeignKey("consultations.consultation_id"),
        nullable=False,
    )
    treatment_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    treatment_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False)

    consultation = relationship(
        "Consultation",
        back_populates="treatments",
    )