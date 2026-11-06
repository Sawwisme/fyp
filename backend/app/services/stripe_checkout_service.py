from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.models import (
    Clinic,
    Payment,
    StripeCheckoutSession,
    User,
)
from app.schemas.stripe_payments import StripeCheckoutResponse
from app.services.order_reservation_service import _lock_order
from app.services.pet_service import get_owner_profile
from app.services.stripe_gateway import (
    get_stripe_client,
    get_webhook_secret,
)
from app.services.stripe_reservation_service import (
    validate_remote_session,
)
from app.services.stripe_session_service import resolve_remote_session


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_return_url():
    base = config.STRIPE_RETURN_BASE_URL

    try:
        parsed = urlsplit(base)
        parsed.port  # Validate the port if supplied.
    except ValueError:
        raise HTTPException(
            503,
            "Stripe return URL is not configured correctly.",
        ) from None

    local_http = (
        parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1"}
    )

    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or (parsed.scheme != "https" and not local_http)
    ):
        raise HTTPException(
            503,
            "Stripe return URL is not configured correctly.",
        )

    return base + "/shop/payments/stripe/return"


def lock_payment_state(
    db: Session,
    owner_id: int,
    order_id: int,
):
    order = _lock_order(
        db,
        order_id,
        owner_id=owner_id,
    )

    if order is None:
        raise HTTPException(404, "Order not found.")

    clinic_status = db.scalar(
        select(Clinic.status)
        .where(Clinic.clinic_id == order.clinic_id)
        .with_for_update()
    )

    if clinic_status != "active":
        raise HTTPException(409, "Clinic shop unavailable.")

    if (
        order.order_status != "pending_payment"
        or order.stock_released_at is not None
    ):
        raise HTTPException(
            409,
            "This order is no longer awaiting payment.",
        )

    if (
        order.payment_expires_at is None
        or order.payment_expires_at <= utc_now()
    ):
        raise HTTPException(
            409,
            "The payment deadline has passed. Refresh your order.",
        )

    payments = db.scalars(
        select(Payment)
        .where(Payment.order_id == order.order_id)
        .order_by(Payment.payment_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()

    if not payments or any(
        payment.payment_status == "paid"
        for payment in payments
    ):
        raise HTTPException(
            409,
            "This order cannot start another payment.",
        )

    payment = payments[-1]

    if (
        payment.payment_status != "pending"
        or payment.payment_method not in {"online_banking", "card"}
        or payment.amount != order.total_amount
        or payment.payment_date is not None
    ):
        raise HTTPException(
            409,
            "The order's payment record needs checking.",
        )

    checkout = db.scalar(
        select(StripeCheckoutSession)
        .where(StripeCheckoutSession.order_id == order.order_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    return order, payment, checkout


def create_or_reopen_checkout(
    db: Session,
    current_user: User,
    order_id: int,
):
    # Check configuration before saving a new payment attempt.
    get_stripe_client()
    get_webhook_secret()
    return_url = get_return_url()

    try:
        owner = get_owner_profile(db, current_user)
        owner_id = owner.pet_owner_id

        order, payment, checkout = lock_payment_state(
            db,
            owner_id,
            order_id,
        )

        amount_cents = int(order.total_amount * 100)

        # FPX B2C accepts MYR 1.00 to MYR 30,000.00.
        if not 100 <= amount_cents <= 3000000:
            raise HTTPException(
                422,
                "FPX orders must be between RM 1.00 and RM 30,000.00.",
            )

        if checkout is None:
            metadata = {
                "order_id": str(order.order_id),
                "payment_id": str(payment.payment_id),
            }

            payload = {
                "mode": "payment",
                "allowed_payment_method_types": ["fpx", "card"],
                "client_reference_id": str(order.order_id),
                "customer_email": current_user.email,
                "metadata": metadata,
                "payment_intent_data": {
                    "metadata": dict(metadata),
                },
                "line_items": [
                    {
                        "price_data": {
                            "currency": "myr",
                            "unit_amount": amount_cents,
                            "product_data": {
                                "name": f"VetDental order #{order.order_id}",
                            },
                        },
                        "quantity": 1,
                    }
                ],
                "success_url": return_url,
                "cancel_url": return_url,
            }

            checkout = StripeCheckoutSession(
                order_id=order.order_id,
                payment_id=payment.payment_id,
                idempotency_key=str(uuid4()),
                amount_cents=amount_cents,
                currency="myr",
                request_payload=payload,
                session_status="creating",
                created_at=utc_now(),
                # This is our local reservation deadline.
                expires_at=order.payment_expires_at,
            )

            db.add(checkout)

        elif (
            checkout.payment_id != payment.payment_id
            or checkout.amount_cents != amount_cents
            or checkout.currency != "myr"
        ):
            raise HTTPException(
                409,
                "The saved payment request does not match this order.",
            )

        # Save the request before contacting Stripe.
        # A timeout can then be recovered using exactly the same request.
        db.commit()

    except Exception:
        db.rollback()
        raise

    try:
        # Recheck after the commit: cancellation or expiry may have intervened.
        order, payment, checkout = lock_payment_state(
            db,
            owner_id,
            order_id,
        )

        if checkout is None:
            raise HTTPException(
                409,
                "Saved payment request unavailable. Refresh the order.",
            )

        if checkout.payment_id != payment.payment_id:
            raise HTTPException(
                409,
                "The order's payment record changed.",
            )

        remote = resolve_remote_session(checkout)
        validate_remote_session(remote, checkout, order)

        checkout.session_status = remote.get("status")
        checkout.checkout_url = None

        if (
            remote.get("status") != "open"
            or remote.get("payment_status") != "unpaid"
        ):
            # Preserve a recovered session ID for webhook reconciliation.
            db.commit()

            raise HTTPException(
                409,
                "The Stripe session is already completed or expired. "
                "Refresh the order to check its payment status.",
            )

        if order.payment_expires_at <= utc_now():
            db.commit()

            raise HTTPException(
                409,
                "The payment deadline has passed. Refresh the order.",
            )

        checkout_url = remote.get("url")

        if not isinstance(checkout_url, str):
            raise HTTPException(502, "Stripe returned no payment URL.")

        parsed = urlsplit(checkout_url)

        if (
            parsed.scheme != "https"
            or parsed.hostname != "checkout.stripe.com"
            or parsed.username
            or parsed.password
        ):
            raise HTTPException(
                502,
                "Stripe returned an unexpected payment URL.",
            )

        checkout.checkout_url = checkout_url

        result = StripeCheckoutResponse(
            order_id=order.order_id,
            checkout_url=checkout_url,
            expires_at=order.payment_expires_at,
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise