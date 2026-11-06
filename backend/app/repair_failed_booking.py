from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Transaction
from app.services.booking_payment_state import (
    lock_booking_payment_context,
)
from app.services.booking_payment_processor import (
    close_expired_booking,
)


APPOINTMENT_ID = 8

# Matches the rejected request shown in your Stripe screenshot.
REJECTED_KEY = "815d34bf-0acf-4756-b856-e4fa58b62bf5"


def main():
    with SessionLocal() as db:
        try:
            context = lock_booking_payment_context(
                db, APPOINTMENT_ID
            )

            appointment = context[4]
            payments = context[5]
            checkouts = context[6]

            if len(payments) != 1 or len(checkouts) != 1:
                raise RuntimeError(
                    "Unexpected payment attempts. Nothing changed."
                )

            payment = payments[0]
            checkout = checkouts[0]

            if (
                appointment.status == "cancelled"
                and payment.payment_status == "expired"
                and checkout.session_status == "expired"
            ):
                print("Booking #8 is already closed.")
                return

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            payload = checkout.request_payload or {}

            safe_to_close = (
                appointment.status == "pending_payment"
                and appointment.payment_expires_at is not None
                and appointment.payment_expires_at <= now
                and payment.payment_status == "pending"
                and payment.gateway_reference is None
                and payment.receipt_number is None
                and payment.payment_date is None
                and payment.amount == appointment.booking_deposit_amount
                and checkout.payment_id == payment.payment_id
                and checkout.session_status == "creating"
                and checkout.stripe_session_id is None
                and checkout.checkout_url is None
                and checkout.idempotency_key == REJECTED_KEY
                and payload.get("payment_method_types") == ["fpx"]
                and payload.get("client_reference_id") == "booking:8"
            )

            if not safe_to_close:
                raise RuntimeError(
                    "The booking no longer matches the rejected "
                    "request. Nothing changed."
                )

            transaction_id = db.scalar(
                select(Transaction.transaction_id)
                .where(Transaction.payment_id == payment.payment_id)
                .limit(1)
            )

            if transaction_id is not None:
                raise RuntimeError(
                    "A transaction exists. Nothing changed."
                )

            close_expired_booking(
                db, context, payment, checkout
            )

            if (
                appointment.status != "cancelled"
                or payment.payment_status != "expired"
                or checkout.session_status != "expired"
            ):
                raise RuntimeError(
                    "Booking needs reconciliation. Nothing changed."
                )

            db.commit()
            print("Booking #8 cancelled; unpaid attempt expired.")
            print(f"Slot status: {context[3].status}")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()