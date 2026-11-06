import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from stripe import StripeError

from app.models import (
    OrderStatusHistory,
    Payment,
    PetOwner,
    StripeCheckoutSession,
    StripeWebhookEvent,
    Transaction,
)
from app.services.order_reservation_service import (
    _lock_order,
    _release_stock,
)
from app.services.stripe_gateway import get_stripe_client
from app.services.stripe_payment_method_service import verified_payment_method
from app.services.stripe_reservation_service import (
    validate_remote_session,
)
from app.services.stripe_session_service import resolve_remote_session

from app.services.shop_notification_service import notify_shop_event


logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def finish_event(event, status="processed"):
    event.processing_status = status
    event.processed_at = utc_now()


def lock_event(db: Session, event_id: str):
    return db.scalar(
        select(StripeWebhookEvent)
        .where(StripeWebhookEvent.event_id == event_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )


def finish_unmatched_event(db: Session, event_id: str):
    event = lock_event(db, event_id)

    if event is not None and event.processing_status == "pending":
        finish_event(event, "ignored")
        db.commit()
    else:
        db.rollback()


def record_paid(
    db: Session,
    order,
    payment,
    checkout,
    remote: dict,
    client,
):
    intent_id = remote.get("payment_intent")

    if (
        not isinstance(intent_id, str)
        or not intent_id.startswith("pi_")
        or len(intent_id) > 100
    ):
        raise HTTPException(409, "Missing payment reference.")

    intent = client.v1.payment_intents.retrieve(
        intent_id,
        params={"expand": ["latest_charge"]},
    ).to_dict()

    metadata = intent.get("metadata") or {}

    if (
        intent.get("id") != intent_id
        or intent.get("livemode") is not False
        or intent.get("status") != "succeeded"
        or intent.get("currency") != checkout.currency
        or intent.get("amount") != checkout.amount_cents
        or intent.get("amount_received") != checkout.amount_cents
        or metadata.get("order_id") != str(order.order_id)
        or metadata.get("payment_id") != str(payment.payment_id)
        or payment.amount != order.total_amount
        or payment.gateway_reference not in (None, intent_id)
    ):
        raise HTTPException(
            409,
            "Stripe payment verification did not match the order.",
        )

    payment.payment_method = verified_payment_method(intent, payment)

    payer_user_id = db.scalar(
        select(PetOwner.user_id)
        .where(PetOwner.pet_owner_id == order.pet_owner_id)
    )

    if payer_user_id is None:
        raise HTTPException(409, "Payment owner unavailable.")

    transaction = db.scalar(
        select(Transaction)
        .where(
            Transaction.payment_id == payment.payment_id,
            Transaction.transaction_type == "payment",
        )
        .with_for_update()
    )

    if transaction is not None and (
        transaction.order_id != order.order_id
        or transaction.user_id != payer_user_id
        or transaction.amount != order.total_amount
        or transaction.transaction_status != "completed"
    ):
        raise HTTPException(
            409,
            "The payment transaction needs reconciliation.",
        )
    
    if payment.payment_status == "refunded":
        if (
            transaction is None
            or order.order_status != "refunded"
        ):
            raise HTTPException(
                409,
                "The refunded payment needs reconciliation.",
            )

        checkout.session_status = "complete"
        checkout.checkout_url = None
        return True

    now = utc_now()

    payment.payment_status = "paid"
    payment.gateway_reference = intent_id

    if payment.payment_date is None:
        payment.payment_date = now

    if transaction is None:
        db.add(
            Transaction(
                user_id=payer_user_id,
                order_id=order.order_id,
                payment_id=payment.payment_id,
                transaction_type="payment",
                amount=order.total_amount,
                transaction_status="completed",
                transaction_date=now,
            )
        )

    checkout.session_status = "complete"
    checkout.checkout_url = None

    if (
        order.order_status == "pending_payment"
        and order.stock_released_at is None
    ):
        previous_status = order.order_status
        order.order_status = "paid"
        order.version += 1

        db.add(
            OrderStatusHistory(
                order_id=order.order_id,
                changed_by_user_id=None,
                previous_status=previous_status,
                new_status="paid",
                resulting_version=order.version,
                notes="Stripe sandbox payment verified by the system.",
                created_at=now,
            )
        )

        
        notify_shop_event(
            db,
            order,
            event_key=f"shop:order:{order.order_id}:paid",
            title="Order payment confirmed",
            message=(
                f"Online payment for order #{order.order_id} "
                "was verified. The clinic can now prepare the order."
            ),
            include_owner=True,
            include_admins=True,
        )

        return True

    # A repeated event must not change a fulfilled order or deduct stock.
    if order.order_status in {
        "paid",
        "processing",
        "ready_for_pickup",
        "shipped",
        "completed",
    } and order.stock_released_at is None:
        return True

    notify_shop_event(
        db,
        order,
        event_key=f"shop:order:{order.order_id}:payment-review",
        title="Order payment needs review",
        message=(
            f"Payment was received for closed order "
            f"#{order.order_id}. Contact the clinic to "
            "resolve the payment. Do not pay again."
        ),
        include_owner=True,
        include_admins=True,
    )

    # Preserve the financial record if money arrived for a closed order.
    # Do not reopen it or take stock from another order.
    logger.warning(
        "Paid Stripe order %s requires manual review",
        order.order_id,
    )
    return False


def process_event(db: Session, event_id: str):
    try:
        initial = db.get(StripeWebhookEvent, event_id)

        if initial is None or initial.processing_status != "pending":
            db.rollback()
            return

        session_id = initial.session_id
        client = get_stripe_client()

        hint = db.scalar(
            select(StripeCheckoutSession)
            .where(
                StripeCheckoutSession.stripe_session_id == session_id
            )
        )

        if hint is not None:
            order_id = hint.order_id
        else:
            # Recover the order hint if the session-creation response was lost.
            remote_hint = client.v1.checkout.sessions.retrieve(
                session_id
            ).to_dict()

            metadata = remote_hint.get("metadata") or {}
            candidate = metadata.get("order_id", "")

            if (
                not isinstance(candidate, str)
                or not candidate.isascii()
                or not candidate.isdigit()
                or len(candidate) > 10
                or not 1 <= int(candidate) <= 2147483647
            ):
                # CLI fixture events do not belong to an application order.
                finish_unmatched_event(db, event_id)
                return

            order_id = int(candidate)

        # Match the lock order used by cancellation and fulfilment.
        order = _lock_order(db, order_id)

        if order is None:
            finish_unmatched_event(db, event_id)
            return

        payments = db.scalars(
            select(Payment)
            .where(Payment.order_id == order.order_id)
            .order_by(Payment.payment_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        ).all()

        checkout = db.scalar(
            select(StripeCheckoutSession)
            .where(StripeCheckoutSession.order_id == order.order_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        event = lock_event(db, event_id)

        if event is None or event.processing_status != "pending":
            db.rollback()
            return

        if checkout is None:
            finish_event(event, "ignored")
            db.commit()
            return

        payment = next(
            (
                item for item in payments
                if item.payment_id == checkout.payment_id
            ),
            None,
        )

        if payment is None:
            raise HTTPException(409, "Linked payment unavailable.")

        remote = resolve_remote_session(checkout)

        if checkout.stripe_session_id != session_id:
            finish_event(event, "ignored")
            db.commit()
            return

        validate_remote_session(remote, checkout, order)

        if (
            remote.get("status") == "complete"
            and remote.get("payment_status") == "paid"
        ):
            accepted = record_paid(
                db,
                order,
                payment,
                checkout,
                remote,
                client,
            )

            finish_event(
                event,
                "processed" if accepted else "review_required",
            )

        elif (
            remote.get("status") == "expired"
            and remote.get("payment_status") == "unpaid"
        ):
            if (
                order.order_status == "pending_payment"
                and order.stock_released_at is None
            ):
                _release_stock(
                    db,
                    order,
                    status="expired",
                    actor_user_id=None,
                )

            checkout.session_status = "expired"
            checkout.checkout_url = None
            finish_event(event)

        elif remote.get("status") == "open":
            # It is still unpaid. The existing expiry worker manages its deadline.
            checkout.session_status = "open"
            finish_event(event)

        elif (
            event.event_type == "checkout.session.async_payment_failed"
        ):
            # Do not release stock from an unresolved completed payment.
            # Flag this exceptional case for reconciliation.
            checkout.session_status = "review_required"
            finish_event(event, "review_required")

            logger.warning(
                "Stripe payment for order %s requires review",
                order.order_id,
            )

        else:
            # A completed asynchronous payment can still await confirmation.
            # Keep the event pending so the worker checks it again.
            checkout.session_status = remote.get("status") or "creating"

        db.commit()

    except StripeError:
        db.rollback()
        raise HTTPException(
            503,
            "Stripe payment verification is temporarily unavailable.",
        ) from None

    except Exception:
        db.rollback()
        raise