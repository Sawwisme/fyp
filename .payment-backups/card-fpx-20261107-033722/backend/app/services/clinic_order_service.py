from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from datetime import datetime, timezone

from uuid import uuid4

from app.models import Order, User, Clinic, OrderStatusHistory, Payment, PetOwner, Transaction, Refund
from app.schemas.clinic_orders import ClinicOrderListResponse, ClinicOrderStatusUpdate
from app.services.admin_profile_service import get_admin_record
from app.services.shop_order_service import build_order_response
from app.services.order_reservation_service import _release_stock
from app.services.shop_notification_service import notify_shop_event

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

        refund_in_progress = db.scalar(
            select(Refund.refund_id)
            .join(
                Transaction,
                Transaction.transaction_id
                == Refund.transaction_id,
            )
            .where(
                Transaction.order_id == order.order_id,
                Refund.status.in_([
                    "approved",
                    "processing",
                    "requires_action",
                    "succeeded",
                    "failed",
                ]),
            )
            .limit(1)
        )

        if refund_in_progress is not None:
            raise HTTPException(
                409,
                "This order has an approved refund. "
                "Resolve the refund before changing fulfilment.",
            )
        
        if order.version != data.expected_version:
            raise HTTPException(
                409,
                "This order changed. Reload its details before continuing.",
            )

        payments = db.scalars(
            select(Payment)
            .where(Payment.order_id == order.order_id)
            .order_by(Payment.payment_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        ).all()

        if not payments:
            raise HTTPException(409, "Payment record unavailable.")

        payment = payments[-1]

        if payment.amount != order.total_amount:
            raise HTTPException(
                409,
                "Payment amount does not match the order.",
            )

        if order.stock_released_at is not None:
            raise HTTPException(
                409,
                "This order's stock has already been released.",
            )

        cash = payment.payment_method == "cash"
        previous_status = order.order_status
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        collected_cash = False

        if cash:
            if (
                order.shipping_method != "pickup"
                or payment.payment_status not in {"pending", "paid"}
            ):
                raise HTTPException(
                    409,
                    "Invalid cash pickup payment state.",
                )

            transitions = {
                "confirmed": "processing",
                "processing": "ready_for_pickup",
                "ready_for_pickup": "completed",
            }
        else:
            if (
                payment.payment_method != "online_banking"
                or payment.payment_status != "paid"
                or payment.payment_date is None
            ):
                raise HTTPException(
                    409,
                    "Confirmed online payment is required "
                    "before processing this order.",
                )

            if order.shipping_method == "pickup":
                transitions = {
                    "paid": "processing",
                    "processing": "ready_for_pickup",
                    "ready_for_pickup": "completed",
                }
            elif order.shipping_method == "delivery":
                transitions = {
                    "paid": "processing",
                    "processing": "shipped",
                    "shipped": "completed",
                }
            else:
                raise HTTPException(409, "Invalid shipping method.")

        if data.cash_received and not (
            cash and data.new_status == "completed"
        ):
            raise HTTPException(
                422,
                "Cash collection can only be confirmed "
                "when completing a cash pickup order.",
            )

        if data.new_status == "cancelled":
            if (
                not cash
                or payment.payment_status != "pending"
                or order.order_status not in {
                    "confirmed",
                    "processing",
                    "ready_for_pickup",
                }
            ):
                raise HTTPException(
                    409,
                    "Only an unpaid cash pickup order can be "
                    "cancelled through this action.",
                )

            if not data.notes or len(data.notes) < 5:
                raise HTTPException(
                    422,
                    "Enter a cancellation reason of at least 5 characters.",
                )

            _release_stock(
                db,
                order,
                status="cancelled",
                actor_user_id=current_user.user_id,
            )

            # _release_stock also increments the order version.

        else:
            if transitions.get(order.order_status) != data.new_status:
                raise HTTPException(
                    409,
                    "This status change is not allowed.",
                )

            if (
                cash
                and payment.payment_status == "pending"
                and data.new_status == "completed"
            ):
                if not data.cash_received:
                    raise HTTPException(
                        422,
                        "Confirm that the full cash amount was received.",
                    )

                if any(
                    item.payment_status == "paid"
                    for item in payments
                ):
                    raise HTTPException(
                        409,
                        "Another payment has already been recorded.",
                    )

                payer_user_id = db.scalar(
                    select(PetOwner.user_id)
                    .where(
                        PetOwner.pet_owner_id == order.pet_owner_id
                    )
                )

                if payer_user_id is None:
                    raise HTTPException(
                        409,
                        "The order's owner account is unavailable.",
                    )

                existing_transaction = db.scalar(
                    select(Transaction)
                    .where(
                        Transaction.payment_id == payment.payment_id,
                        Transaction.transaction_type == "payment",
                    )
                    .with_for_update()
                )

                if existing_transaction is not None:
                    raise HTTPException(
                        409,
                        "A payment transaction already exists. "
                        "Reload the order before continuing.",
                    )

                payment.payment_status = "paid"
                payment.payment_date = now
                payment.receipt_number = (
                    payment.receipt_number or f"CASH-{uuid4().hex}"
                )

                db.add(
                    Transaction(
                        user_id=payer_user_id,
                        order_id=order.order_id,
                        payment_id=payment.payment_id,
                        transaction_type="payment",
                        amount=order.total_amount,
                        transaction_status="completed",
                        transaction_date=now,
                    )
                )

                collected_cash = True

            elif cash and payment.payment_status == "paid":
                if payment.payment_date is None:
                    raise HTTPException(
                        409,
                        "The cash payment record needs checking.",
                    )

            order.order_status = data.new_status
            order.version += 1

        db.add(
            OrderStatusHistory(
                order_id=order.order_id,
                changed_by_user_id=current_user.user_id,
                previous_status=previous_status,
                new_status=order.order_status,
                resulting_version=order.version,
                notes=(
                    data.notes
                    or (
                        "Cash received in full and order collected."
                        if collected_cash
                        else None
                    )
                ),
                created_at=now,
            )
        )

        owner_messages = {
            "processing": (
                "Your order is being prepared",
                f"The clinic is preparing order #{order.order_id}.",
            ),
            "ready_for_pickup": (
                "Your order is ready for pickup",
                f"Order #{order.order_id} is ready. "
                "Please collect it from the clinic.",
            ),
            "shipped": (
                "Your order has been shipped",
                f"Order #{order.order_id} has been "
                "handed over for delivery.",
            ),
            "completed": (
                "Your order is completed",
                f"Order #{order.order_id} has been completed.",
            ),
            "cancelled": (
                "Your order was cancelled",
                f"The clinic cancelled order #{order.order_id}. "
                "Open the order or contact the clinic for details.",
            ),
        }

        notification = owner_messages.get(order.order_status)

        if notification is not None:
            title, notification_message = notification

            notify_shop_event(
                db,
                order,
                event_key=(
                    f"shop:order:{order.order_id}:"
                    f"{order.order_status}"
                ),
                title=title,
                message=notification_message,
            )

        # Stock was reserved when the order was placed.
        # Collection and fulfilment do not deduct stock again.
        db.flush()
        result = build_order_response(db, order)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise