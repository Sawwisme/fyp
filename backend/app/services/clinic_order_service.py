from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from datetime import datetime, timezone

from app.models import Order, User, Clinic, OrderStatusHistory, Payment
from app.schemas.clinic_orders import ClinicOrderListResponse, ClinicOrderStatusUpdate
from app.services.admin_profile_service import get_admin_record
from app.services.shop_order_service import build_order_response


def _clinic_orders(clinic_id: int):
    return select(Order).where(
        Order.clinic_id == clinic_id,
        Order.checkout_key.is_not(None),
    )


def list_clinic_orders(
    db: Session,
    current_user: User,
    q: str,
    order_status: str | None,
    shipping_method: str | None,
    offset: int,
    limit: int,
):
    admin = get_admin_record(db, current_user)

    statement = _clinic_orders(admin.clinic_id)

    query = q.strip()

    if query:
        conditions = [
            Order.recipient_name.contains(query, autoescape=True),
            Order.recipient_phone.contains(query, autoescape=True),
        ]

        # Also support searching an order number such as 12 or #12.
        order_number = query.removeprefix("#")

        if (
            order_number.isascii()
            and order_number.isdigit()
            and len(order_number) <= 10
        ):
            order_id = int(order_number)

            if 1 <= order_id <= 2147483647:
                conditions.append(Order.order_id == order_id)

        statement = statement.where(or_(*conditions))

    if order_status:
        statement = statement.where(
            Order.order_status == order_status
        )

    if shipping_method:
        statement = statement.where(
            Order.shipping_method == shipping_method
        )

    total = db.scalar(
        select(func.count()).select_from(
            statement.order_by(None).subquery()
        )
    ) or 0

    orders = db.scalars(
        statement
        .options(
            selectinload(Order.items),
            selectinload(Order.clinic),
        )
        .order_by(
            Order.order_date.desc(),
            Order.order_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return ClinicOrderListResponse(
        total=total,
        items=[
            build_order_response(db, order)
            for order in orders
        ],
    )


def get_clinic_order(
    db: Session,
    current_user: User,
    order_id: int,
):
    admin = get_admin_record(db, current_user)

    order = db.scalar(
        _clinic_orders(admin.clinic_id)
        .where(Order.order_id == order_id)
        .options(
            selectinload(Order.items),
            selectinload(Order.clinic),
        )
    )

    if order is None:
        raise HTTPException(404, "Order not found.")

    return build_order_response(db, order)

def update_order_status(
    db: Session,
    current_user: User,
    order_id: int,
    data: ClinicOrderStatusUpdate,
):
    try:
        admin = get_admin_record(db, current_user)

        # Use the same lock order as checkout and stock release:
        # clinic, order, then payment.
        clinic = db.scalar(
            select(Clinic)
            .where(Clinic.clinic_id == admin.clinic_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if clinic is None or clinic.status != "active":
            raise HTTPException(403, "Clinic unavailable.")

        order = db.scalar(
            _clinic_orders(admin.clinic_id)
            .where(Order.order_id == order_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if order is None:
            raise HTTPException(404, "Order not found.")

        if order.version != data.expected_version:
            raise HTTPException(
                409,
                "This order changed. Reload its details before continuing.",
            )

        payment = db.scalar(
            select(Payment)
            .where(Payment.order_id == order.order_id)
            .order_by(Payment.payment_id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if (
            payment is None
            or payment.payment_status != "paid"
            or payment.amount != order.total_amount
            or payment.payment_date is None
        ):
            raise HTTPException(
                409,
                "Confirmed payment is required before processing this order.",
            )

        if order.stock_released_at is not None:
            raise HTTPException(
                409,
                "Reserved stock was released. This order cannot be fulfilled.",
            )

        transitions = {
            "pickup": {
                "paid": "processing",
                "processing": "ready_for_pickup",
                "ready_for_pickup": "completed",
            },
            "delivery": {
                "paid": "processing",
                "processing": "shipped",
                "shipped": "completed",
            },
        }

        allowed_next = transitions.get(
            order.shipping_method, {}
        ).get(order.order_status)

        if allowed_next != data.new_status:
            raise HTTPException(
                409,
                "This status change is not allowed for the current order.",
            )

        previous_status = order.order_status
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        order.order_status = data.new_status
        order.version += 1

        db.add(
            OrderStatusHistory(
                order_id=order.order_id,
                changed_by_user_id=current_user.user_id,
                previous_status=previous_status,
                new_status=order.order_status,
                resulting_version=order.version,
                notes=data.notes or None,
                created_at=now,
            )
        )

        # Stock was already reserved when the order was placed.
        # Fulfilment must not deduct it again.
        db.flush()

        result = build_order_response(db, order)
        db.commit()

        return result

    except Exception:
        db.rollback()
        raise