from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from fastapi import HTTPException

from app.models import BillingStripeSession, Payment
from app.schemas.owner_billing import BillCheckoutResponse
from app.services.billing_payment_state import (
    lock_bill_payment_context,
)
from app.services.billing_stripe_gateway import (
    expected_metadata,
    validate_bill_session,
)
from app.services.pet_service import get_owner_profile
from app.services.stripe_checkout_service import get_return_url
from app.services.stripe_gateway import get_stripe_client
from app.services.stripe_session_service import resolve_remote_session
from app.services.bill_deposit_validation import (
    validate_bill_deposit,
)


def ensure_payable(db, clinic, bill, appointment):
    if clinic.status != "active":
        raise HTTPException(
            409,
            "This clinic is not accepting online payments.",
        )

    if (
        bill.status != "issued"
        or bill.issued_at is None
        or bill.consultation.status != "completed"
        or appointment.status != "completed"
    ):
        raise HTTPException(
            409,
            "This bill is not awaiting payment. Refresh its details.",
        )

    validate_bill_deposit(
        db,
        bill,
        appointment,
    )

    cents = int(bill.balance_amount * 100)

    if not 100 <= cents <= 3000000:
        raise HTTPException(
            422,
            "FPX bill payments must be between "
            "RM 1.00 and RM 30,000.00. "
            "Contact the clinic for another payment method.",
        )

    return cents


def find_pending_attempt(payments, checkouts):
    active = [
        payment
        for payment in payments
        if payment.payment_status not in {
            "failed",
            "cancelled",
            "expired",
        }
    ]

    if len(active) > 1:
        raise HTTPException(
            409,
            "Multiple payment records need reconciliation.",
        )

    if active:
        payment = active[0]

        checkout = next(
            (
                item
                for item in checkouts
                if item.payment_id == payment.payment_id
            ),
            None,
        )

        if (
            payment.payment_status != "pending"
            or payment.payment_method != "online_banking"
            or payment.payment_purpose != "consultation_balance"
            or payment.order_id is not None
            or checkout is None
            or checkout.session_status not in {
                "creating",
                "open",
                "processing",
            }
        ):
            raise HTTPException(
                409,
                "An existing payment must be resolved first.",
            )

        return payment, checkout

    # Do not replace an unresolved Stripe request just because
    # its local payment record has an unexpected status.
    if any(
        item.session_status not in {"expired", "failed"}
        for item in checkouts
    ):
        raise HTTPException(
            409,
            "A previous payment session needs reconciliation.",
        )

    for payment in payments:
        if payment.payment_method == "online_banking":
            matching = next(
                (
                    item
                    for item in checkouts
                    if item.payment_id == payment.payment_id
                ),
                None,
            )

            if matching is None:
                raise HTTPException(
                    409,
                    "A previous online payment has no session record.",
                )

    return None, None


def create_or_reopen_checkout(db, current_user, bill_id):
    get_stripe_client()

    # Reuse the existing trusted return-origin validation,
    # with a bill-specific return page.
    parsed = urlsplit(get_return_url())
    return_url = urlunsplit((
        parsed.scheme,
        parsed.netloc,
        "/owner-billing/stripe/return",
        "",
        "",
    ))

    try:
        owner = get_owner_profile(db, current_user)
        owner_id = owner.pet_owner_id

        clinic, bill, appointment, payments, checkouts = (
            lock_bill_payment_context(
                db,
                bill_id,
                owner_id=owner_id,
            )
        )

        amount_cents = ensure_payable(
            db, clinic, bill, appointment
        )

        payment, checkout = find_pending_attempt(
            payments, checkouts
        )

        if checkout is None:
            payment = Payment(
                order_id=None,
                appointment_id=appointment.appointment_id,
                consultation_bill_id=bill.consultation_bill_id,
                payment_purpose="consultation_balance",
                payment_method="online_banking",
                payment_status="pending",
                amount=bill.balance_amount,
            )

            db.add(payment)
            db.flush()

            checkout = BillingStripeSession(
                consultation_bill_id=bill.consultation_bill_id,
                payment_id=payment.payment_id,
                idempotency_key=str(uuid4()),
                amount_cents=amount_cents,
                currency="myr",
                session_status="creating",
                created_at=datetime.now(timezone.utc).replace(
                    tzinfo=None
                ),
            )

            metadata = expected_metadata(
                checkout, bill, appointment
            )

            checkout.request_payload = {
                "mode": "payment",
                "allowed_payment_method_types": ["fpx"],
                "client_reference_id": (
                    f"bill:{bill.consultation_bill_id}"
                ),
                "customer_email": current_user.email,
                "metadata": metadata,
                "payment_intent_data": {
                    "metadata": dict(metadata),
                },
                "line_items": [{
                    "price_data": {
                        "currency": "myr",
                        "unit_amount": amount_cents,
                        "product_data": {
                            "name": (
                                "VetDental consultation bill "
                                f"#{bill.consultation_bill_id}"
                            ),
                        },
                    },
                    "quantity": 1,
                }],
                "success_url": return_url,
                "cancel_url": return_url,
            }

            db.add(checkout)
            db.flush()

        if (
            payment.amount != bill.balance_amount
            or checkout.amount_cents != amount_cents
            or checkout.currency != "myr"
        ):
            raise HTTPException(
                409,
                "The saved payment amount needs reconciliation.",
            )

        checkout_id = checkout.billing_checkout_id

        # Persist the exact request and retry key before Stripe.
        db.commit()

    except Exception:
        db.rollback()
        raise

    try:
        clinic, bill, appointment, payments, checkouts = (
            lock_bill_payment_context(
                db,
                bill_id,
                owner_id=owner_id,
            )
        )

        ensure_payable(db, clinic, bill, appointment)

        checkout = next(
            (
                item
                for item in checkouts
                if item.billing_checkout_id == checkout_id
            ),
            None,
        )

        payment = next(
            (
                item
                for item in payments
                if checkout is not None
                and item.payment_id == checkout.payment_id
            ),
            None,
        )

        if (
            checkout is None
            or payment is None
            or payment.payment_status != "pending"
        ):
            raise HTTPException(
                409,
                "The payment state changed. Refresh the bill.",
            )

        remote = resolve_remote_session(checkout)

        validate_bill_session(
            remote,
            checkout,
            bill,
            payment,
            appointment,
        )

        checkout.checkout_url = None

        if (
            remote.get("status") != "open"
            or remote.get("payment_status") != "unpaid"
        ):
            # Keep the recovered session ID and let the worker
            # verify its final state. Do not create a replacement.
            checkout.session_status = "processing"
            db.commit()

            raise HTTPException(
                409,
                "This payment session is completed or closed. "
                "Refresh the bill shortly to check its saved status.",
            )

        checkout_url = remote.get("url")
        expiry = remote.get("expires_at")

        if (
            not isinstance(checkout_url, str)
            or not isinstance(expiry, int)
            or isinstance(expiry, bool)
        ):
            raise HTTPException(
                502,
                "Unexpected Stripe checkout response.",
            )

        url = urlsplit(checkout_url)

        if (
            url.scheme != "https"
            or url.hostname != "checkout.stripe.com"
            or url.username
            or url.password
        ):
            raise HTTPException(
                502,
                "Stripe returned an unexpected payment URL.",
            )

        expires_at = datetime.fromtimestamp(
            expiry,
            tz=timezone.utc,
        ).replace(tzinfo=None)

        if expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
            checkout.session_status = "processing"
            db.commit()

            raise HTTPException(
                409,
                "This payment session has expired. "
                "Refresh the bill shortly.",
            )

        checkout.session_status = "open"
        checkout.checkout_url = checkout_url
        checkout.expires_at = expires_at

        result = BillCheckoutResponse(
            consultation_bill_id=bill.consultation_bill_id,
            checkout_url=checkout_url,
            expires_at=expires_at,
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise