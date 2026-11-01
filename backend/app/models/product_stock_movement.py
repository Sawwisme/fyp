from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)

from app.database import Base


def stock_movement_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ProductStockMovement(Base):
    __tablename__ = "product_stock_movements"

    __table_args__ = (
        CheckConstraint(
            "quantity_change <> 0",
            name="chk_stock_movement_change",
        ),
        CheckConstraint(
            "quantity_before >= 0 "
            "AND quantity_after >= 0 "
            "AND quantity_after = quantity_before + quantity_change",
            name="chk_stock_movement_quantities",
        ),
        Index(
            "ix_stock_movement_product_created",
            "product_id",
            "created_at",
            "movement_id",
        ),
    )

    movement_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    product_id = Column(
        Integer,
        ForeignKey("products.product_id"),
        nullable=False,
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    quantity_change = Column(Integer, nullable=False)
    quantity_before = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)

    reason = Column(String(1000), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=stock_movement_utc_now,
    )