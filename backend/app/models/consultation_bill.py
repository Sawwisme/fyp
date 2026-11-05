from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ConsultationBill(Base):
    __tablename__ = "consultation_bills"

    __table_args__ = (
        UniqueConstraint(
            "consultation_id",
            name="uq_consultation_bill_consultation",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="chk_consultation_bill_total",
        ),
        CheckConstraint(
            "status IN ('draft', 'issued', 'paid', 'void')",
            name="chk_consultation_bill_status",
        ),
        Index(
            "ix_consultation_bill_clinic_status",
            "clinic_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_consultation_bill_owner_created",
            "pet_owner_id",
            "created_at",
        ),
    )

    consultation_bill_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    consultation_id = Column(
        Integer,
        ForeignKey("consultations.consultation_id"),
        nullable=False,
    )

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.clinic_id"),
        nullable=False,
    )

    pet_owner_id = Column(
        Integer,
        ForeignKey("pet_owners.pet_owner_id"),
        nullable=False,
    )

    status = Column(
        String(20),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
    )

    total_amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default=text("0.00"),
    )

    version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    created_by_user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    issued_by_user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    issued_at = Column(DateTime, nullable=True)

    consultation = relationship("Consultation")
    clinic = relationship("Clinic")
    owner = relationship("PetOwner")

    items = relationship(
        "ConsultationBillItem",
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="ConsultationBillItem.consultation_bill_item_id",
    )