from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Clinic,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductStockMovement,
    User,
)
from app.services.pet_service import get_owner_profile
from app.services.stripe_reservation_service import (
    close_checkout_before_stock_release,
)

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _lock_order(
    db: Session,
    order_id: int,
    owner_id: int | None = None,
):
    location = select(Order.clinic_id).where(
        Order.order_id == order_id,
        Order.checkout_key.is_not(None),
        Order.clinic_id.is_not(None),
    )

    if owner_id is not None:
        location = location.where(
            Order.pet_owner_id == owner_id,
        )

    clinic_id = db.scalar(location)

    if clinic_id is None:
        return None

    # Expiry must also work if the clinic has become inactive.
    db.scalar(
        select(Clinic)
        .where(Clinic.clinic_id == clinic_id)
        .with_for_update()
    )

    statement = select(Order).where(
        Order.order_id == order_id,
        Order.clinic_id == clinic_id,
    )

    if owner_id is not None:
        statement = statement.where(
            Order.pet_owner_id == owner_id,
        )

    return db.scalar(
        statement
        .execution_options(populate_existing=True)
        .with_for_update()
    )


def _release_stock(
    db: Session,
    order: Order,
    status: str,
    actor_user_id: int | None,
):
    if order.order_status != "pending_payment":
        raise HTTPException(
            409,
            "Only an unpaid pending order can release reserved stock.",
        )

    if order.stock_released_at is not None:
        raise HTTPException(
            409,
            "This order's stock has already been released.",
        )

    payments = db.scalars(
        select(Payment)
        .where(Payment.order_id == order.order_id)
        .order_by(Payment.payment_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    if any(payment.payment_status == "paid" for payment in payments):
        raise HTTPException(
            409,
            "Payment has been received. This order cannot be cancelled "
            "as an unpaid order.",
        )
    
    close_checkout_before_stock_release(db, order)

    items = db.scalars(
        select(OrderItem)
        .where(OrderItem.order_id == order.order_id)
        .order_by(OrderItem.product_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    reservations = {
        movement.product_id: movement
        for movement in db.scalars(
            select(ProductStockMovement)
            .where(
                ProductStockMovement.reference_order_id == order.order_id,
                ProductStockMovement.movement_type == "order_reserved",
            )
            .with_for_update()
        ).all()
    }

    if not items or len(reservations) != len(items):
        raise HTTPException(
            409,
            "Order reservation records need checking.",
        )

    now = utc_now()

    for item in items:
        reservation = reservations.get(item.product_id)

        if (
            reservation is None
            or item.quantity <= 0
            or reservation.quantity_change != -item.quantity
        ):
            raise HTTPException(
                409,
                "Order reservation quantities do not match.",
            )

        product = db.scalar(
            select(Product)
            .where(
                Product.product_id == item.product_id,
                Product.clinic_id == order.clinic_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if product is None:
            raise HTTPException(
                409,
                "A reserved product could not be found.",
            )

        before = product.stock_quantity
        after = before + item.quantity

        if after > 2147483647:
            raise HTTPException(409, "Stock quantity is too large.")

        product.stock_quantity = after
        product.version += 1
        product.updated_at = now

        db.add(
            ProductStockMovement(
                product_id=product.product_id,
                created_by_user_id=actor_user_id,
                quantity_change=item.quantity,
                quantity_before=before,
                quantity_after=after,
                reason=(
                    f"Reserved stock returned: order "
                    f"#{order.order_id} {status}."
                ),
                movement_type="order_released",
                reference_order_id=order.order_id,
            )
        )

    for payment in payments:
        if payment.payment_status == "pending":
            payment.payment_status = (
                "expired" if status == "expired" else "cancelled"
            )

    order.order_status = status
    order.stock_released_at = now
    order.version += 1


def expire_unpaid_order(
    db: Session,
    order_id: int,
):
    try:
        order = _lock_order(db, order_id)

        if (
            order is None
            or order.order_status != "pending_payment"
            or order.payment_expires_at is None
            or order.payment_expires_at > utc_now()
        ):
            db.rollback()
            return False

        _release_stock(
            db,
            order,
            status="expired",
            actor_user_id=None,
        )

        db.commit()
        return True

    except Exception:
        db.rollback()
        raise


def cancel_my_unpaid_order(
    db: Session,
    current_user: User,
    order_id: int,
):
    try:
        owner = get_owner_profile(db, current_user)
        order = _lock_order(
            db,
            order_id,
            owner_id=owner.pet_owner_id,
        )

        if order is None:
            raise HTTPException(404, "Order not found.")

        if order.order_status not in ("cancelled", "expired"):
            status = (
                "expired"
                if (
                    order.payment_expires_at is not None
                    and order.payment_expires_at <= utc_now()
                )
                else "cancelled"
            )

            _release_stock(
                db,
                order,
                status=status,
                actor_user_id=current_user.user_id,
            )

        result = {
            "order_id": order.order_id,
            "order_status": order.order_status,
        }

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise