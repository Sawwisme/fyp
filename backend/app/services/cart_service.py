from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Cart,
    CartItem,
    Clinic,
    PetOwner,
    Product,
    User,
)
from app.schemas.cart import CartQuantityUpdate, CartResponse
from app.services.pet_service import get_owner_profile


def _build_cart(
    db: Session,
    owner_id: int,
    clinic: Clinic,
):
    cart = db.scalar(
        select(Cart)
        .where(
            Cart.pet_owner_id == owner_id,
            Cart.clinic_id == clinic.clinic_id,
        )
    )

    items = []

    if cart is not None:
        records = db.execute(
            select(CartItem, Product)
            .join(
                Product,
                Product.product_id == CartItem.product_id,
            )
            .where(CartItem.cart_id == cart.cart_id)
            .order_by(CartItem.cart_item_id)
        ).all()

        for item, product in records:
            available = (
                clinic.status == "active"
                and product.clinic_id == clinic.clinic_id
                and product.status == "active"
                and product.price > 0
                and product.stock_quantity >= item.quantity
            )

            items.append({
                "product_id": product.product_id,
                "product_name": product.product_name,
                "image_url": product.image_url,
                "quantity": item.quantity,
                "stock_quantity": product.stock_quantity,
                "unit_price": product.price,
                "line_total": product.price * item.quantity,
                "available": available,
                "price_changed": product.price != item.unit_price,
            })

    return CartResponse(
        cart_id=cart.cart_id if cart is not None else None,
        clinic_id=clinic.clinic_id,
        clinic_name=clinic.clinic_name,
        version=cart.version if cart is not None else 0,
        items=items,
        item_count=len(items),
        total_quantity=sum(item["quantity"] for item in items),
        subtotal=sum(
            (item["line_total"] for item in items),
            Decimal("0.00"),
        ),
        can_checkout=(
            bool(items)
            and all(item["available"] for item in items)
        ),
    )


def get_my_cart(
    db: Session,
    current_user: User,
    clinic_id: int,
):
    owner = get_owner_profile(db, current_user)
    clinic = db.get(Clinic, clinic_id)

    if clinic is None:
        raise HTTPException(404, "Clinic not found.")

    return _build_cart(db, owner.pet_owner_id, clinic)


def set_cart_quantity(
    db: Session,
    current_user: User,
    clinic_id: int,
    product_id: int,
    data: CartQuantityUpdate,
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

        cart = db.scalar(
            select(Cart)
            .where(
                Cart.pet_owner_id == owner.pet_owner_id,
                Cart.clinic_id == clinic_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        current_version = cart.version if cart is not None else 0

        if current_version != data.expected_version:
            raise HTTPException(
                409,
                "Your cart changed. Reload it before updating quantities.",
            )

        item = None

        if cart is not None:
            item = db.scalar(
                select(CartItem)
                .where(
                    CartItem.cart_id == cart.cart_id,
                    CartItem.product_id == product_id,
                )
                .with_for_update()
            )

        if data.quantity == 0:
            if item is not None:
                db.delete(item)

        else:
            if clinic.status != "active":
                raise HTTPException(409, "This clinic shop is unavailable.")

            product = db.scalar(
                select(Product)
                .where(
                    Product.product_id == product_id,
                    Product.clinic_id == clinic_id,
                    Product.status == "active",
                )
                .execution_options(populate_existing=True)
                .with_for_update()
            )

            if product is None or product.price <= 0:
                raise HTTPException(409, "This product is unavailable.")

            if data.quantity > product.stock_quantity:
                raise HTTPException(
                    409,
                    "The requested quantity exceeds available stock.",
                )

            if cart is None:
                cart = Cart(
                    pet_owner_id=owner.pet_owner_id,
                    clinic_id=clinic_id,
                    version=1,
                )
                db.add(cart)
                db.flush()

            if item is None:
                count = db.scalar(
                    select(func.count(CartItem.cart_item_id))
                    .where(CartItem.cart_id == cart.cart_id)
                )

                if int(count or 0) >= 50:
                    raise HTTPException(
                        422,
                        "A cart can contain up to 50 different products.",
                    )

                item = CartItem(
                    cart_id=cart.cart_id,
                    product_id=product.product_id,
                    quantity=data.quantity,
                    unit_price=product.price,
                )
                db.add(item)

            else:
                item.quantity = data.quantity
                item.unit_price = product.price

        if cart is not None:
            cart.version = current_version + 1
            cart.updated_at = datetime.now(
                timezone.utc
            ).replace(tzinfo=None)

        db.flush()

        result = _build_cart(db, owner.pet_owner_id, clinic)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise