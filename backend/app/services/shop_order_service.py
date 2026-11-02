import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Cart,
    CartItem,
    Clinic,
    Order,
    OrderItem,
    Payment,
    PetOwner,
    Product,
    ProductStockMovement,
    User,
)
from app.schemas.shop_orders import ShopOrderCreate, ShopOrderResponse
from app.services.pet_service import get_owner_profile


def _fingerprint(clinic_id: int, data: ShopOrderCreate) -> str:
    payload = data.model_dump(mode="json")
    payload["clinic_id"] = clinic_id
    payload["expected_total_amount"] = format(
        data.expected_total_amount, ".2f"
    )
    payload["owner_note"] = data.owner_note or None

    if data.shipping_method == "pickup":
        payload["delivery_address"] = None

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def build_order_response(db: Session, order: Order):
    payment = db.scalar(
        select(Payment)
        .where(Payment.order_id == order.order_id)
        .order_by(Payment.payment_id.desc())
        .limit(1)
    )

    return ShopOrderResponse(
        order_id=order.order_id,
        checkout_key=order.checkout_key,
        version=order.version,
        clinic_id=order.clinic_id,
        clinic_name=order.clinic.clinic_name,
        order_status=order.order_status,
        payment_status=(
            payment.payment_status if payment is not None else "unavailable"
        ),
        shipping_method=order.shipping_method,
        shipping_address=order.shipping_address,
        recipient_name=order.recipient_name,
        recipient_phone=order.recipient_phone,
        owner_note=order.owner_note,
        subtotal=order.subtotal,
        shipping_fee=order.shipping_fee,
        total_amount=order.total_amount,
        order_date=order.order_date,
        payment_expires_at=order.payment_expires_at,
        items=sorted(
            order.items,
            key=lambda item: item.order_item_id,
        ),
    )


def create_order(
    db: Session,
    current_user: User,
    clinic_id: int,
    data: ShopOrderCreate,
):
    try:
        profile = get_owner_profile(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(Clinic.clinic_id == clinic_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(404, "Clinic not found.")

        owner = db.scalar(
            select(PetOwner)
            .where(
                PetOwner.pet_owner_id == profile.pet_owner_id,
                PetOwner.user_id == current_user.user_id,
            )
            .with_for_update()
        )

        if owner is None:
            raise HTTPException(403, "Owner profile unavailable.")

        checkout_key = str(data.checkout_key)
        fingerprint = _fingerprint(clinic_id, data)

        existing = db.scalar(
            select(Order)
            .where(
                Order.pet_owner_id == owner.pet_owner_id,
                Order.checkout_key == checkout_key,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if existing is not None:
            if (
                existing.clinic_id != clinic_id
                or existing.checkout_fingerprint != fingerprint
            ):
                raise HTTPException(
                    409,
                    "This checkout key belongs to a different request.",
                )

            result = build_order_response(db, existing)
            db.commit()
            return result

        if clinic.status != "active":
            raise HTTPException(409, "Clinic shop unavailable.")

        if clinic.shop_version != data.expected_settings_version:
            raise HTTPException(
                409,
                "Delivery settings changed. Reload checkout.",
            )

        cart = db.scalar(
            select(Cart)
            .where(
                Cart.pet_owner_id == owner.pet_owner_id,
                Cart.clinic_id == clinic_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if (
            cart is None
            or cart.version != data.expected_cart_version
        ):
            raise HTTPException(
                409,
                "Your cart changed. Review it before ordering.",
            )

        cart_items = db.scalars(
            select(CartItem)
            .where(CartItem.cart_id == cart.cart_id)
            .order_by(CartItem.product_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        ).all()

        if not cart_items:
            raise HTTPException(422, "Your cart is empty.")

        if len(cart_items) > 50:
            raise HTTPException(422, "Too many products in the cart.")

        products = {
            product.product_id: product
            for product in db.scalars(
                select(Product)
                .where(
                    Product.product_id.in_([
                        item.product_id for item in cart_items
                    ])
                )
                .order_by(Product.product_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            ).all()
        }

        subtotal = Decimal("0.00")

        for item in cart_items:
            product = products.get(item.product_id)

            if (
                product is None
                or product.clinic_id != clinic_id
                or product.status != "active"
                or product.price <= 0
            ):
                raise HTTPException(
                    409,
                    "A cart product is no longer available.",
                )

            if not 1 <= item.quantity <= 99:
                raise HTTPException(422, "Invalid cart quantity.")

            if item.quantity > product.stock_quantity:
                raise HTTPException(
                    409,
                    f"Insufficient stock for {product.product_name}.",
                )

            subtotal += product.price * item.quantity

        if data.shipping_method == "pickup":
            if not clinic.shop_pickup_enabled:
                raise HTTPException(409, "Pickup is unavailable.")

            address = (clinic.address or "").strip()

            if not address:
                raise HTTPException(
                    409,
                    "The clinic has no pickup address.",
                )

            shipping_fee = Decimal("0.00")
        else:
            if not clinic.shop_delivery_enabled:
                raise HTTPException(409, "Delivery is unavailable.")

            address = data.delivery_address
            shipping_fee = clinic.shop_delivery_fee

        total = subtotal + shipping_fee

        if total > Decimal("99999999.99"):
            raise HTTPException(422, "The order total is too large.")

        if total != data.expected_total_amount:
            raise HTTPException(
                409,
                "Product prices changed. Reload checkout "
                "and review the new total.",
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        order = Order(
            clinic_id=clinic_id,
            pet_owner_id=owner.pet_owner_id,
            created_by_user_id=current_user.user_id,
            checkout_key=checkout_key,
            checkout_fingerprint=fingerprint,
            recipient_name=data.recipient_name,
            recipient_phone=data.recipient_phone,
            owner_note=data.owner_note or None,
            shipping_address=address,
            shipping_method=data.shipping_method,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            total_amount=total,
            order_status="pending_payment",
            order_date=now,
            payment_expires_at=now + timedelta(minutes=15),
            version=1,
        )

        db.add(order)
        db.flush()

        for item in cart_items:
            product = products[item.product_id]
            before = product.stock_quantity

            order.items.append(
                OrderItem(
                    product_id=product.product_id,
                    product_name=product.product_name,
                    quantity=item.quantity,
                    unit_price=product.price,
                    subtotal=product.price * item.quantity,
                )
            )

            product.stock_quantity -= item.quantity
            product.version += 1
            product.updated_at = now

            db.add(
                ProductStockMovement(
                    product_id=product.product_id,
                    created_by_user_id=current_user.user_id,
                    quantity_change=-item.quantity,
                    quantity_before=before,
                    quantity_after=product.stock_quantity,
                    reason=f"Stock reserved for order #{order.order_id}.",
                    movement_type="order_reserved",
                    reference_order_id=order.order_id,
                )
            )

            db.delete(item)

        db.add(
            Payment(
                order_id=order.order_id,
                payment_method="online_banking",
                payment_status="pending",
                amount=total,
            )
        )

        cart.version += 1
        cart.updated_at = now

        db.flush()
        result = build_order_response(db, order)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def get_my_order(
    db: Session,
    current_user: User,
    order_id: int,
):
    owner = get_owner_profile(db, current_user)

    order = db.scalar(
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.clinic),
        )
        .where(
            Order.order_id == order_id,
            Order.pet_owner_id == owner.pet_owner_id,
            Order.checkout_key.is_not(None),
            Order.clinic_id.is_not(None),
        )
    )

    if order is None:
        raise HTTPException(404, "Order not found.")

    return build_order_response(db, order)


def get_my_order_by_key(
    db: Session,
    current_user: User,
    checkout_key: str,
):
    owner = get_owner_profile(db, current_user)

    order = db.scalar(
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.clinic),
        )
        .where(
            Order.pet_owner_id == owner.pet_owner_id,
            Order.checkout_key == checkout_key,
            Order.clinic_id.is_not(None),
        )
    )

    if order is None:
        raise HTTPException(404, "Order not found.")

    return build_order_response(db, order)


def list_my_orders(
    db: Session,
    current_user: User,
    offset: int,
    limit: int,
):
    owner = get_owner_profile(db, current_user)

    orders = db.scalars(
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.clinic),
        )
        .where(
            Order.pet_owner_id == owner.pet_owner_id,
            Order.checkout_key.is_not(None),
            Order.clinic_id.is_not(None),
        )
        .order_by(Order.order_date.desc(), Order.order_id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return [
        build_order_response(db, order)
        for order in orders
    ]