from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from stripe import StripeError

from app.models import BillingStripeSession, StripeCheckoutSession
from app.services.stripe_gateway import get_stripe_client


def resolve_remote_session(
    checkout: StripeCheckoutSession | BillingStripeSession,
) -> dict:
    client = get_stripe_client()

    try:
        if checkout.stripe_session_id:
            return client.v1.checkout.sessions.retrieve(
                checkout.stripe_session_id
            ).to_dict()

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Stripe may remove idempotency records after 24 hours.
        # An old uncertain request needs reconciliation rather than recreation.
        if (
            checkout.created_at is None
            or now - checkout.created_at >= timedelta(hours=23)
        ):
            raise HTTPException(
                409,
                "This payment request requires manual reconciliation.",
            )

        remote = client.v1.checkout.sessions.create(
            params=checkout.request_payload,
            options={
                "idempotency_key": checkout.idempotency_key,
            },
        ).to_dict()

        session_id = remote.get("id")

        if (
            not isinstance(session_id, str)
            or not session_id.startswith("cs_test_")
            or len(session_id) > 255
            or remote.get("livemode") is not False
        ):
            raise HTTPException(
                502,
                "Unexpected Stripe sandbox response.",
            )

        checkout.stripe_session_id = session_id

        # An idempotency retry can replay the original creation response.
        # Retrieve the session again to obtain its current payment state.
        return client.v1.checkout.sessions.retrieve(
            session_id
        ).to_dict()

    except StripeError:
        raise HTTPException(
            503,
            "Cannot confirm the Stripe payment session. "
            "Retry this order; a new payment request will not be created.",
        ) from None