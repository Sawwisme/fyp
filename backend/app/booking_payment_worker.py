import logging

from fastapi import HTTPException
from sqlalchemy import select

from app.database import SessionLocal
from app.models import BookingStripeSession
from app.services.booking_payment_processor import (
    sync_booking_checkout,
)


logger = logging.getLogger(__name__)


def run_pass(stop_event, after_id):
    with SessionLocal() as db:
        checkout_ids = db.scalars(
            select(BookingStripeSession.booking_checkout_id)
            .where(
                BookingStripeSession.booking_checkout_id > after_id,
                BookingStripeSession.session_status.in_([
                    "creating",
                    "open",
                    "processing",
                ]),
            )
            .order_by(BookingStripeSession.booking_checkout_id)
            .limit(10)
        ).all()

    if not checkout_ids:
        return 0

    for checkout_id in checkout_ids:
        if stop_event.is_set():
            return after_id

        try:
            with SessionLocal() as db:
                sync_booking_checkout(db, checkout_id)

        except HTTPException as exc:
            logger.warning(
                "Booking checkout %s deferred (HTTP %s)",
                checkout_id,
                exc.status_code,
            )

        except Exception:
            logger.exception(
                "Could not sync booking checkout %s",
                checkout_id,
            )

        after_id = checkout_id

    return after_id


def run_worker(stop_event):
    after_id = 0

    while not stop_event.is_set():
        try:
            after_id = run_pass(stop_event, after_id)

        except Exception:
            logger.exception(
                "Booking payment status check failed"
            )

        stop_event.wait(15)