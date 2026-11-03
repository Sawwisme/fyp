from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.database import get_db
from app.services import stripe_webhook_service


router = APIRouter(
    prefix="/shop/payments/stripe",
    tags=["Stripe Payments"],
)


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    # Read the original bytes without modifying the JSON.
    maximum_size = 1024 * 1024
    payload = bytearray()

    async for chunk in request.stream():
        if len(payload) + len(chunk) > maximum_size:
            raise HTTPException(
                413,
                "Webhook payload is too large.",
            )

        payload.extend(chunk)

    signature = request.headers.get("stripe-signature", "")

    event = stripe_webhook_service.verify_event(
        bytes(payload),
        signature,
    )

    return await run_in_threadpool(
        stripe_webhook_service.save_event,
        db,
        event,
    )