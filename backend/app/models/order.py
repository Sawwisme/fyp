from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        UniqueConstraint(
            "pet_owner_id",
            "checkout_key",
            name="uq_order_owner_checkout",
        ),
        Index(
            "ix_order_clinic_status_date",
            "clinic_id",
            "order_status",
            "order_date",
        ),
        Index(
            "ix_order_payment_expiry",
            "order_status",
            "payment_expires_at",
        ),
    )
    order_id = Column(Integer, primary_key=True, autoincrement=True)
    pet_owner_id = Column(
        Integer,
        ForeignKey("pet_owners.pet_owner_id"),
        nullable=False,
    )
    order_date = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    shipping_address = Column(String(500), nullable=False)
    shipping_method = Column(String(50), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)
    shipping_fee = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    order_status = Column(String(30), nullable=False)
    clinic_id = Column(
        Integer,
        ForeignKey("clinics.clinic_id"),
        nullable=True,
    )

    created_by_user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True,
    )

    recipient_name = Column(String(150), nullable=True)
    recipient_phone = Column(String(20), nullable=True)
    owner_note = Column(String(500), nullable=True)

    checkout_key = Column(String(36), nullable=True)
    checkout_fingerprint = Column(String(64), nullable=True)

    payment_expires_at = Column(DateTime, nullable=True)
    stock_released_at = Column(DateTime, nullable=True)

    version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    clinic = relationship("Clinic")

    owner = relationship("PetOwner")
    items = relationship("OrderItem", back_populates="order")