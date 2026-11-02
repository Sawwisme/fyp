import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Order
from app.services.order_reservation_service import expire_unpaid_order


logger = logging.getLogger(__name__)


def run_pass(stop_event):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with SessionLocal() as db:
        order_ids = db.scalars(
            select(Order.order_id)
            .where(
                Order.order_status == "pending_payment",
                Order.checkout_key.is_not(None),
                Order.clinic_id.is_not(None),
                Order.payment_expires_at.is_not(None),
                Order.payment_expires_at <= now,
            )
            .order_by(
                Order.payment_expires_at,
                Order.order_id,
            )
            .limit(100)
        ).all()

    for order_id in order_ids:
        if stop_event.is_set():
            return

        try:
            with SessionLocal() as db:
                expired = expire_unpaid_order(db, order_id)

            if expired:
                logger.info("Shop order %s expired", order_id)

        except Exception:
            logger.exception(
                "Could not expire shop order %s",
                order_id,
            )


def run_worker(stop_event):
    while not stop_event.is_set():
        try:
            run_pass(stop_event)
        except Exception:
            logger.exception("Shop order expiry check failed")

        stop_event.wait(30)