from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.owner_billing import (
    OwnerBillDetail,
    OwnerBillList,
    BillCheckoutResponse,
    BillOnlineCancelResponse
)
from app.services import owner_billing_service, billing_checkout_service, billing_payment_cancel_service


router = APIRouter(
    prefix="/owner-billing",
    tags=["Owner Consultation Bills"],
)


@router.get(
    "/bills",
    response_model=OwnerBillList,
)
def list_my_bills(
    bill_status: Literal["issued", "paid", "void"] | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return owner_billing_service.list_my_bills(
        db,
        current_user,
        bill_status,
        offset,
        limit,
    )


@router.get(
    "/bills/{bill_id}",
    response_model=OwnerBillDetail,
)
def get_my_bill(
    bill_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return owner_billing_service.get_my_bill(
        db,
        current_user,
        bill_id,
    )

@router.post(
    "/bills/{bill_id}/checkout",
    response_model=BillCheckoutResponse,
)
def create_bill_checkout(
    bill_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return billing_checkout_service.create_or_reopen_checkout(
        db,
        current_user,
        bill_id,
    )


@router.get(
    "/stripe/return",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def bill_payment_return():
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
                    padding: 24px;
                    background: #f5f7f5;
                    color: #24352a;
                    font-family: Arial, sans-serif;
                }
                main {
                    max-width: 440px;
                    margin: 60px auto;
                    padding: 28px;
                    border: 1px solid #dce6de;
                    border-radius: 16px;
                    background: white;
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
                    Open Profile → Bills &amp; Receipts and refresh
                    your bill to check payment confirmation.
                </p>
                <p>
                    Returning to this page does not confirm payment.
                </p>
            </main>
        </body>
        </html>
        """
    )

@router.post(
    "/bills/{bill_id}/cancel-online",
    response_model=BillOnlineCancelResponse,
)
def cancel_bill_online_attempt(
    bill_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return billing_payment_cancel_service.cancel_online_attempt(
        db,
        current_user,
        bill_id,
    )