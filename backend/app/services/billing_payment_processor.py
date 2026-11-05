import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from stripe import StripeError

from app.models import (
    BillingStripeSession,
    Notification,
    PetOwner,
    Transaction,
)
from app.services.billing_payment_state import (
    lock_bill_payment_context,
)
from app.services.billing_stripe_gateway import (
    expected_metadata,
    validate_bill_session,
    verify_bill_payment_intent,
)
from app.services.stripe_gateway import get_stripe_client
from app.services.stripe_session_service import resolve_remote_session


logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def record_verified_payment(
    db,
    bill,
    appointment,
    payments,
    payment,
    checkout,
    remote,
):
    intent_id = verify_bill_payment_intent(
        remote,
        checkout,
        bill,
        payment,
        appointment,
    )

    payer_user_id = db.scalar(
        select(PetOwner.user_id)
        .where(PetOwner.pet_owner_id == bill.pet_owner_id)
    )

    transaction = db.scalar(
        select(Transaction)
        .where(
            Transaction.payment_id == payment.payment_id,
            Transaction.transaction_type == "payment",
        )
        .with_for_update()
    )

    if transaction is not None and (
        transaction.order_id is not None
        or transaction.user_id != payer_user_id
        or transaction.amount != payment.amount
        or transaction.transaction_status != "completed"
    ):
        raise HTTPException(
            409,
            "The bill payment transaction needs reconciliation.",
        )

    # Never overwrite a previously refunded payment.
    if payment.payment_status == "refunded":
        if transaction is None:
            raise HTTPException(
                409,
                "The refunded payment has no original transaction.",
            )

        checkout.session_status = "complete"
        checkout.checkout_url = None
        return

    previously_paid = payment.payment_status == "paid"

    another_paid = any(
        item.payment_id != payment.payment_id
        and item.payment_status == "paid"
        for item in payments
    )

    now = utc_now()

    payment.payment_status = "paid"
    payment.gateway_reference = intent_id
    payment.payment_date = payment.payment_date or now
    payment.receipt_number = (
        payment.receipt_number
        or f"BILL-ONLINE-{uuid4().hex}"
    )

    if transaction is None:
        db.add(
            Transaction(
                user_id=payer_user_id,
                order_id=None,
                payment_id=payment.payment_id,
                transaction_type="payment",
                amount=payment.amount,
                transaction_status="completed",
                transaction_date=now,
            )
        )

    checkout.session_status = "complete"
    checkout.checkout_url = None

    if bill.status == "issued" and not another_paid:
        bill.status = "paid"
        bill.version += 1
        bill.updated_at = now

        if payer_user_id is not None:
            db.add(
                Notification(
                    user_id=payer_user_id,
                    event_key=(
                        f"billing:{bill.consultation_bill_id}:paid"
                    ),
                    notification_type="consultation_bill_paid",
                    title="Consultation payment confirmed",
                    message=(
                        f"Online payment of RM {payment.amount:.2f} "
                        f"for bill #{bill.consultation_bill_id} "
                        "was verified."
                    ),
                    resource_type="consultation_bill",
                    resource_id=bill.consultation_bill_id,
                )
            )

        return

    if (
        bill.status == "paid"
        and previously_paid
        and not another_paid
    ):
        return

    # Preserve actual money received, but do not silently
    # overwrite a closed bill or hide a second payment.
    checkout.session_status = "review_required"

    logger.error(
        "Verified payment %s for bill %s requires reconciliation",
        payment.payment_id,
        bill.consultation_bill_id,
    )


def inspect_unpaid_complete(
    checkout,
    bill,
    payment,
    appointment,
    remote,
):
    intent_id = remote.get("payment_intent")

    if not isinstance(intent_id, str) or not intent_id.startswith("pi_"):
        raise HTTPException(409, "Missing pending payment reference.")

    intent = get_stripe_client().v1.payment_intents.retrieve(
        intent_id
    ).to_dict()

    metadata = intent.get("metadata") or {}
    expected = expected_metadata(checkout, bill, appointment)

    if (
        intent.get("id") != intent_id
        or intent.get("livemode") is not False
        or intent.get("currency") != "myr"
        or intent.get("amount") != checkout.amount_cents
        or any(
            metadata.get(key) != value
            for key, value in expected.items()
        )
    ):
        raise HTTPException(
            409,
            "The pending bill payment needs reconciliation.",
        )

    # Only close a failed attempt when Stripe confirms that
    # no money was received and the attempt cannot proceed.
    if (
        intent.get("status") in {
            "requires_payment_method",
            "canceled",
        }
        and intent.get("amount_received") == 0
        and payment.payment_status == "pending"
    ):
        payment.payment_status = "failed"
        checkout.session_status = "failed"
    else:
        checkout.session_status = "processing"

    checkout.checkout_url = None


def sync_bill_checkout(db, checkout_id):
    try:
        initial = db.get(BillingStripeSession, checkout_id)

        if initial is None:
            db.rollback()
            return

        _, bill, appointment, payments, checkouts = (
            lock_bill_payment_context(
                db,
                initial.consultation_bill_id,
            )
        )

        checkout = next(
            (
                item
                for item in checkouts
                if item.billing_checkout_id == checkout_id
            ),
            None,
        )

        if checkout is None:
            raise HTTPException(404, "Bill payment session not found.")

        payment = next(
            (
                item
                for item in payments
                if item.payment_id == checkout.payment_id
            ),
            None,
        )

        if payment is None:
            raise HTTPException(409, "Linked payment unavailable.")

        remote = resolve_remote_session(checkout)

        validate_bill_session(
            remote,
            checkout,
            bill,
            payment,
            appointment,
        )

        expiry = remote.get("expires_at")

        if isinstance(expiry, int) and not isinstance(expiry, bool):
            checkout.expires_at = datetime.fromtimestamp(
                expiry,
                tz=timezone.utc,
            ).replace(tzinfo=None)

        status = remote.get("status")
        payment_status = remote.get("payment_status")

        if status == "complete" and payment_status == "paid":
            record_verified_payment(
                db,
                bill,
                appointment,
                payments,
                payment,
                checkout,
                remote,
            )

        elif status == "expired" and payment_status == "unpaid":
            checkout.checkout_url = None

            if payment.payment_status in {"paid", "refunded"}:
                checkout.session_status = "review_required"
            else:
                checkout.session_status = "expired"

                if payment.payment_status == "pending":
                    payment.payment_status = "expired"

        elif status == "open" and payment_status == "unpaid":
            checkout.session_status = (
                "open"
                if payment.payment_status == "pending"
                else "review_required"
            )

        elif status == "complete" and payment_status == "unpaid":
            if payment.payment_status == "pending":
                inspect_unpaid_complete(
                    checkout,
                    bill,
                    payment,
                    appointment,
                    remote,
                )
            else:
                checkout.session_status = "review_required"

        else:
            raise HTTPException(
                409,
                "Unexpected Stripe bill-payment state.",
            )

        db.commit()

    except StripeError:
        db.rollback()
        raise HTTPException(
            503,
            "Cannot check the bill payment yet.",
        ) from None

    except Exception:
        db.rollback()
        raise