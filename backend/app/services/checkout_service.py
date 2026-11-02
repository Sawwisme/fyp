from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Clinic, User
from app.schemas.checkout import (
    ShopSettingsResponse,
    ShopSettingsUpdate,
    CheckoutQuoteRequest,
    CheckoutQuoteResponse,
)
from app.services.admin_profile_service import get_admin_record
from decimal import Decimal

from app.services.cart_service import _build_cart
from app.services.pet_service import get_owner_profile

def _settings_response(clinic: Clinic):
    return ShopSettingsResponse(
        clinic_id=clinic.clinic_id,
        clinic_name=clinic.clinic_name,
        pickup_enabled=clinic.shop_pickup_enabled,
        delivery_enabled=clinic.shop_delivery_enabled,
        delivery_fee=clinic.shop_delivery_fee,
        pickup_address=clinic.address,
        version=clinic.shop_version,
    )


def get_admin_shop_settings(
    db: Session,
    current_user: User,
):
    administrator = get_admin_record(db, current_user)

    clinic = db.scalar(
        select(Clinic)
        .where(
            Clinic.clinic_id == administrator.clinic_id,
            Clinic.status == "active",
        )
    )

    if clinic is None:
        raise HTTPException(404, "Clinic shop unavailable.")

    return _settings_response(clinic)


def update_shop_settings(
    db: Session,
    current_user: User,
    data: ShopSettingsUpdate,
):
    try:
        administrator = get_admin_record(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == administrator.clinic_id,
                Clinic.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(404, "Clinic shop unavailable.")

        if clinic.shop_version != data.expected_version:
            raise HTTPException(
                409,
                "Shop settings changed. Reload before saving.",
            )

        if data.pickup_enabled and not (clinic.address or "").strip():
            raise HTTPException(
                422,
                "Save the clinic address in your profile "
                "before enabling pickup.",
            )

        clinic.shop_pickup_enabled = data.pickup_enabled
        clinic.shop_delivery_enabled = data.delivery_enabled
        clinic.shop_delivery_fee = data.delivery_fee
        clinic.shop_version += 1
        clinic.updated_at = datetime.now(
            timezone.utc
        ).replace(tzinfo=None)

        db.flush()
        result = _settings_response(clinic)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise

def get_owner_shop_settings(
    db: Session,
    current_user: User,
    clinic_id: int,
):
    get_owner_profile(db, current_user)

    clinic = db.scalar(
        select(Clinic)
        .where(
            Clinic.clinic_id == clinic_id,
            Clinic.status == "active",
        )
    )

    if clinic is None:
        raise HTTPException(404, "Clinic shop unavailable.")

    return _settings_response(clinic)


def get_checkout_quote(
    db: Session,
    current_user: User,
    clinic_id: int,
    data: CheckoutQuoteRequest,
):
    owner = get_owner_profile(db, current_user)

    clinic = db.scalar(
        select(Clinic)
        .where(
            Clinic.clinic_id == clinic_id,
            Clinic.status == "active",
        )
    )

    if clinic is None:
        raise HTTPException(404, "Clinic shop unavailable.")

    cart = _build_cart(db, owner.pet_owner_id, clinic)

    if cart.version != data.expected_cart_version:
        raise HTTPException(
            409,
            "Your cart changed. Return to the cart and review it.",
        )

    if not cart.items:
        raise HTTPException(422, "Your cart is empty.")

    if not cart.can_checkout:
        raise HTTPException(
            409,
            "Some items are unavailable. Review your cart.",
        )

    if data.shipping_method == "pickup":
        if not clinic.shop_pickup_enabled:
            raise HTTPException(409, "Pickup is unavailable.")

        if not (clinic.address or "").strip():
            raise HTTPException(
                409,
                "The clinic has not configured its pickup address.",
            )

        fee = Decimal("0.00")
        pickup_address = clinic.address
    else:
        if not clinic.shop_delivery_enabled:
            raise HTTPException(409, "Delivery is unavailable.")

        fee = clinic.shop_delivery_fee
        pickup_address = None

    total = cart.subtotal + fee

    if total > Decimal("99999999.99"):
        raise HTTPException(
            422,
            "Reduce your cart quantity. The total is too large.",
        )

    return CheckoutQuoteResponse(
        clinic_id=clinic_id,
        clinic_name=clinic.clinic_name,
        cart_version=cart.version,
        settings_version=clinic.shop_version,
        shipping_method=data.shipping_method,
        pickup_address=pickup_address,
        items=cart.items,
        subtotal=cart.subtotal,
        shipping_fee=fee,
        total_amount=total,
    )