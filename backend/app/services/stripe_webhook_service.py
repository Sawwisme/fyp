from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from stripe import SignatureVerificationError, Webhook

from app.models import StripeWebhookEvent
from app.services.stripe_gateway import get_webhook_secret


SUPPORTED_EVENTS = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
    "checkout.session.expired",
}


def verify_event(payload: bytes, signature: str):
    if not signature:
        raise HTTPException(400, "Missing Stripe signature.")

    try:
        event = Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=get_webhook_secret(),
        )
    except (ValueError, UnicodeError, SignatureVerificationError):
        raise HTTPException(
            400,
            "Invalid Stripe webhook payload or signature.",
        ) from None

    event = event.to_dict()
    
    if event.get("livemode") is not False:
        raise HTTPException(
            400,
            "Only Stripe sandbox events are accepted.",
        )

    return event


def save_event(db: Session, event):
    event_type = event.get("type")

    if event_type not in SUPPORTED_EVENTS:
        return {"received": True, "ignored": True}

    event_id = event.get("id")
    data = event.get("data")
    session = data.get("object") if data is not None else None

    session_id = session.get("id") if session is not None else None
    object_type = session.get("object") if session is not None else None

    if (
        not isinstance(event_id, str)
        or not event_id.startswith("evt_")
        or len(event_id) > 255
        or not isinstance(session_id, str)
        or not session_id.startswith("cs_test_")
        or len(session_id) > 255
        or object_type != "checkout.session"
    ):
        raise HTTPException(400, "Invalid checkout event.")

    try:
        db.add(
            StripeWebhookEvent(
                event_id=event_id,
                event_type=event_type,
                session_id=session_id,
                processing_status="pending",
            )
        )

        db.commit()

        return {
            "received": True,
            "duplicate": False,
        }

    except IntegrityError:
        db.rollback()

        # A concurrent or repeated delivery may already have saved it.
        existing = db.get(StripeWebhookEvent, event_id)

        if existing is None:
            raise

        if (
            existing.event_type != event_type
            or existing.session_id != session_id
        ):
            raise HTTPException(
                400,
                "Conflicting Stripe event.",
            )

        return {
            "received": True,
            "duplicate": True,
        }

    except Exception:
        db.rollback()
        raise