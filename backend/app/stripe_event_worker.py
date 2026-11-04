import logging

from sqlalchemy import select

from app.database import SessionLocal
from app.models import StripeWebhookEvent
from app.services.stripe_event_processor import process_event


logger = logging.getLogger(__name__)


def run_pass(stop_event, after_id):
    with SessionLocal() as db:
        event_ids = db.scalars(
            select(StripeWebhookEvent.event_id)
            .where(
                StripeWebhookEvent.processing_status == "pending",
                StripeWebhookEvent.event_id > after_id,
            )
            .order_by(StripeWebhookEvent.event_id)
            .limit(20)
        ).all()

    if not event_ids:
        return ""

    for event_id in event_ids:
        if stop_event.is_set():
            return after_id

        try:
            with SessionLocal() as db:
                process_event(db, event_id)
        except Exception:
            logger.exception(
                "Could not process Stripe event %s; it remains pending",
                event_id,
            )

        after_id = event_id

    # Continue through the queue before retrying unresolved earlier events.
    return after_id


def run_worker(stop_event):
    after_id = ""

    while not stop_event.is_set():
        try:
            after_id = run_pass(stop_event, after_id)
        except Exception:
            logger.exception("Stripe event processing check failed")

        stop_event.wait(5)