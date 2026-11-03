from fastapi import APIRouter, Depends, HTTPException, Path,  Request
from fastapi.responses import HTMLResponse

from app.dependencies import require_roles
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.database import get_db
from app.services import stripe_webhook_service, stripe_checkout_service

from app.models import User
from app.schemas.stripe_payments import StripeCheckoutResponse


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

@router.post(
    "/orders/{order_id}/checkout",
    response_model=StripeCheckoutResponse,
)
def create_checkout(
    order_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return stripe_checkout_service.create_or_reopen_checkout(
        db=db,
        current_user=current_user,
        order_id=order_id,
    )


@router.get(
    "/return",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def payment_return():
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport"
                  content="width=device-width, initial-scale=1">
            <title>VetDental Payment</title>
            <style>
                body {
                    margin: 0;
                    padding: 32px 20px;
                    background: #f5f7f5;
                    color: #24352a;
                    font-family: Arial, sans-serif;
                }
                main {
                    max-width: 440px;
                    margin: 60px auto;
                    padding: 28px;
                    background: white;
                    border: 1px solid #dce6de;
                    border-radius: 16px;
                }
                h1 { color: #176b32; }
                p { line-height: 1.6; }
            </style>
        </head>
        <body>
            <main>
                <h1>VetDental</h1>
                <h2>Return to the app</h2>
                <p>
                    Open My Orders in the VetDental app and refresh
                    your order to check its latest payment status.
                </p>
                <p>You can close this browser page.</p>
            </main>
        </body>
        </html>
        """
    )