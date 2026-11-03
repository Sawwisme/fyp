from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from stripe import StripeError

from app.models import Order, StripeCheckoutSession
from app.services.stripe_gateway import get_stripe_client
from app.services.stripe_session_service import resolve_remote_session


def validate_remote_session(
    remote: dict,
    checkout: StripeCheckoutSession,
    order: Order,
):
    metadata = remote.get("metadata") or {}

    if (
        remote.get("id") != checkout.stripe_session_id
        or remote.get("livemode") is not False
        or remote.get("mode") != "payment"
        or remote.get("client_reference_id") != str(order.order_id)
        or metadata.get("order_id") != str(order.order_id)
        or metadata.get("payment_id") != str(checkout.payment_id)
        or remote.get("currency") != checkout.currency
        or remote.get("amount_total") != checkout.amount_cents
        or checkout.amount_cents != int(order.total_amount * 100)
    ):
        raise HTTPException(
            409,
            "Stripe payment details do not match this order.",
        )


def close_checkout_before_stock_release(
    db: Session,
    order: Order,
):
    # Caller already holds the clinic, order and payment locks.
    checkout = db.scalar(
        select(StripeCheckoutSession)
        .where(
            StripeCheckoutSession.order_id == order.order_id
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    # Orders without a Stripe session keep the existing cancellation flow.
    if checkout is None:
        return

    client = get_stripe_client()

    try:
        remote = resolve_remote_session(checkout)

        validate_remote_session(remote, checkout, order)

        if remote.get("payment_status") == "paid":
            raise HTTPException(
                409,
                "Stripe has received payment. "
                "Wait for payment verification before continuing.",
            )

        if remote.get("status") == "open":
            try:
                remote = client.v1.checkout.sessions.expire(
                    checkout.stripe_session_id
                ).to_dict()
            except StripeError:
                # Payment may have completed while expiry was requested.
                # Retrieve the actual state rather than assuming expiry.
                remote = client.v1.checkout.sessions.retrieve(
                    checkout.stripe_session_id
                ).to_dict()

            validate_remote_session(remote, checkout, order)

        if (
            remote.get("status") != "expired"
            or remote.get("payment_status") != "unpaid"
        ):
            raise HTTPException(
                409,
                "Stripe payment is completed or still being resolved. "
                "Stock has not been released.",
            )

        checkout.session_status = "expired"
        checkout.checkout_url = None

        # The caller commits this together with the stock release.

    except StripeError:
        raise HTTPException(
            503,
            "Cannot confirm that the Stripe payment page is closed. "
            "Stock has not been released. Please try again later.",
        ) from None