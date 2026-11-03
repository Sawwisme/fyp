from fastapi import HTTPException
from stripe import RequestsClient, StripeClient

from app import config


def get_stripe_client() -> StripeClient:
    key = config.STRIPE_SECRET_KEY

    # This integration currently accepts sandbox credentials only.
    if not key.startswith("sk_test_"):
        raise HTTPException(
            status_code=503,
            detail="Stripe sandbox payments are not configured.",
        )

    return StripeClient(
        key,
        http_client=RequestsClient(timeout=10),
        max_network_retries=0,
    )


def get_webhook_secret() -> str:
    secret = config.STRIPE_WEBHOOK_SECRET

    if not secret.startswith("whsec_"):
        raise HTTPException(
            status_code=503,
            detail="Stripe webhook verification is not configured.",
        )

    return secret