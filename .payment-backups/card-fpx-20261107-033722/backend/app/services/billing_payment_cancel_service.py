from fastapi import HTTPException
from sqlalchemy import select
from stripe import StripeError

from app.models import Transaction
from app.schemas.owner_billing import BillOnlineCancelResponse
from app.services.billing_payment_state import (
    lock_bill_payment_context,
)
from app.services.billing_stripe_gateway import validate_bill_session
from app.services.consultation_billing_service import utc_now
from app.services.pet_service import get_owner_profile
from app.services.stripe_gateway import get_stripe_client
from app.services.stripe_session_service import resolve_remote_session


CLOSED_PAYMENT_STATUSES = {
    "failed",
    "cancelled",
    "expired",
}


def cancel_online_attempt(db, current_user, bill_id):
    try:
        owner = get_owner_profile(db, current_user)

        _, bill, appointment, payments, checkouts = (
            lock_bill_payment_context(
                db,
                bill_id,
                owner_id=owner.pet_owner_id,
            )
        )

        if bill.status != "issued":
            raise HTTPException(
                409,
                "This bill is already settled or no longer payable.",
            )

        active = [
            payment
            for payment in payments
            if payment.payment_status not in CLOSED_PAYMENT_STATUSES
        ]

        if not active:
            if any(
                checkout.session_status not in {"expired", "failed"}
                for checkout in checkouts
            ):
                raise HTTPException(
                    409,
                    "A payment session still needs reconciliation.",
                )

            result = BillOnlineCancelResponse(
                consultation_bill_id=bill.consultation_bill_id,
                payment_attempt_closed=True,
            )

            db.commit()
            return result

        if len(active) != 1:
            raise HTTPException(
                409,
                "Multiple payment records need reconciliation.",
            )

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
            or payment.payment_date is not None
            or checkout is None
        ):
            raise HTTPException(
                409,
                "This payment cannot be cancelled as an unpaid attempt.",
            )

        existing_transaction = db.scalar(
            select(Transaction.transaction_id)
            .where(Transaction.payment_id == payment.payment_id)
            .limit(1)
        )

        if existing_transaction is not None:
            raise HTTPException(
                409,
                "A financial transaction already exists for this payment.",
            )

        remote = resolve_remote_session(checkout)

        validate_bill_session(
            remote,
            checkout,
            bill,
            payment,
            appointment,
        )

        if (
            remote.get("status") == "open"
            and remote.get("payment_status") == "unpaid"
        ):
            client = get_stripe_client()

            try:
                remote = client.v1.checkout.sessions.expire(
                    checkout.stripe_session_id
                ).to_dict()

            except StripeError:
                # Payment may have completed during cancellation.
                # Check Stripe's current state instead of assuming expiry.
                remote = client.v1.checkout.sessions.retrieve(
                    checkout.stripe_session_id
                ).to_dict()

            validate_bill_session(
                remote,
                checkout,
                bill,
                payment,
                appointment,
            )

        if (
            remote.get("status") != "expired"
            or remote.get("payment_status") != "unpaid"
        ):
            checkout.session_status = "processing"
            checkout.checkout_url = None

            # Preserve the recovered reference for verification.
            db.commit()

            raise HTTPException(
                409,
                "Payment has completed or is still being resolved. "
                "Refresh the bill shortly. Do not pay cash yet.",
            )

        checkout.session_status = "expired"
        checkout.checkout_url = None

        payment.payment_status = "cancelled"

        bill.version += 1
        bill.updated_at = utc_now()

        result = BillOnlineCancelResponse(
            consultation_bill_id=bill.consultation_bill_id,
            payment_attempt_closed=True,
        )

        db.commit()
        return result

    except StripeError:
        db.rollback()
        raise HTTPException(
            503,
            "Cannot confirm that the Stripe page is closed. "
            "Do not pay cash until the payment status is checked.",
        ) from None

    except Exception:
        db.rollback()
        raise