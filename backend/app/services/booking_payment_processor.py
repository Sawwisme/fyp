import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from stripe import StripeError

from app.clinic_time import CLINIC_TIMEZONE
from app.models import (
    Appointment,
    BookingStripeSession,
    Notification,
    PetOwner,
    Transaction,
)
from app.services.booking_payment_state import (
    lock_booking_payment_context,
)
from app.services.booking_stripe_gateway import (
    validate_booking_session,
    verify_booking_payment_intent,
    expected_metadata,
    validate_booking_session,
    verify_booking_payment_intent,
)
from app.services.stripe_gateway import get_stripe_client
from app.services.stripe_session_service import resolve_remote_session
from app.services.vet_absence_service import reject_vet_absence


logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def vet_is_available(db, veterinarian, schedule, slot):
    try:
        reject_vet_absence(
            db,
            veterinarian.veterinarian_id,
            schedule.schedule_date,
            slot.start_time,
            slot.end_time,
        )
        return True

    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        return False


def another_appointment_uses_slot(db, appointment, slot):
    return db.scalar(
        select(Appointment.appointment_id)
        .where(
            Appointment.time_slot_id == slot.time_slot_id,
            Appointment.appointment_id
            != appointment.appointment_id,
            Appointment.status.notin_(["cancelled", "rejected"]),
        )
        .limit(1)
        .with_for_update()
    ) is not None


def mark_for_review(checkout, appointment):
    checkout.session_status = "review_required"
    checkout.checkout_url = None

    logger.error(
        "Booking checkout %s for appointment %s needs review",
        checkout.booking_checkout_id,
        appointment.appointment_id,
    )


def record_verified_deposit(
    db,
    context,
    payment,
    checkout,
    remote,
):
    (
        clinic,
        veterinarian,
        schedule,
        slot,
        appointment,
        payments,
        _,
    ) = context

    intent_id = verify_booking_payment_intent(
        remote,
        checkout,
        payment,
        appointment,
    )

    payer_user_id = db.scalar(
        select(PetOwner.user_id)
        .where(
            PetOwner.pet_owner_id == appointment.pet_owner_id,
        )
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
            "The deposit transaction needs reconciliation.",
        )

    if payment.payment_status in {
        "refunded",
        "partially_refunded",
    }:
        if transaction is None:
            raise HTTPException(
                409,
                "The refunded deposit has no original transaction.",
            )

        checkout.session_status = "complete"
        checkout.checkout_url = None
        return

    previous_status = payment.payment_status

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
        or f"BOOKING-{uuid4().hex}"
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

    # Repeated verification must not repeat confirmation.
    if (
        previous_status == "paid"
        and not another_paid
        and appointment.status in {
            "confirmed",
            "in_progress",
            "completed",
        }
    ):
        return

    if (
        appointment.status != "pending_payment"
        or previous_status not in {"pending", "paid"}
        or another_paid
    ):
        mark_for_review(checkout, appointment)
        return

    start = datetime.combine(
        schedule.schedule_date,
        slot.start_time,
        tzinfo=CLINIC_TIMEZONE,
    )

    can_confirm = (
        clinic.status == "active"
        and veterinarian.approval_status == "approved"
        and veterinarian.user.status == "active"
        and veterinarian.user.role == "veterinarian"
        and schedule.status == "active"
        and slot.status == "booked"
        and start > datetime.now(CLINIC_TIMEZONE)
        and not another_appointment_uses_slot(
            db, appointment, slot
        )
        and vet_is_available(
            db, veterinarian, schedule, slot
        )
    )

    if not can_confirm:
        # Preserve actual money received without silently
        # confirming a cancelled or unavailable booking.
        mark_for_review(checkout, appointment)
        return

    appointment.status = "confirmed"
    from app.services.staff_notification_service import notify_booking_confirmed
    notify_booking_confirmed(db, appointment)

    if payer_user_id is not None:
        db.add(
            Notification(
                user_id=payer_user_id,
                event_key=(
                    f"booking:{appointment.appointment_id}:"
                    "deposit-confirmed"
                ),
                notification_type="booking_deposit_paid",
                title="Appointment confirmed",
                message=(
                    f"Your deposit of RM {payment.amount:.2f} "
                    f"for appointment #{appointment.appointment_id} "
                    "was verified. Your appointment is confirmed."
                ),
                resource_type="appointment",
                resource_id=appointment.appointment_id,
            )
        )


def close_expired_booking(
    db,
    context,
    payment,
    checkout,
):
    (
        _,
        veterinarian,
        schedule,
        slot,
        appointment,
        payments,
        checkouts,
    ) = context

    other_active_payment = any(
        item.payment_id != payment.payment_id
        and item.payment_status not in {
            "failed",
            "cancelled",
            "expired",
        }
        for item in payments
    )

    other_active_checkout = any(
        item.booking_checkout_id != checkout.booking_checkout_id
        and item.session_status not in {"expired", "failed"}
        for item in checkouts
    )

    if (
        payment.payment_status in {"paid", "refunded"}
        or other_active_payment
        or other_active_checkout
        or appointment.status not in {
            "pending_payment",
            "cancelled",
        }
    ):
        mark_for_review(checkout, appointment)
        return

    checkout.session_status = "expired"
    checkout.checkout_url = None

    if payment.payment_status == "pending":
        payment.payment_status = "expired"

    if appointment.status == "pending_payment":
        appointment.status = "cancelled"

    # Queries below must see this booking as cancelled.
    db.flush()

    if (
        slot.status == "booked"
        and schedule.status == "active"
        and not another_appointment_uses_slot(
            db, appointment, slot
        )
    ):
        slot.status = (
            "available"
            if vet_is_available(
                db, veterinarian, schedule, slot
            )
            else "blocked"
        )

def inspect_unpaid_checkout(
    db,
    context,
    payment,
    checkout,
    remote,
):
    appointment = context[4]
    intent_id = remote.get("payment_intent")

    if (
        not isinstance(intent_id, str)
        or not intent_id.startswith("pi_")
        or len(intent_id) > 100
    ):
        raise HTTPException(
            409,
            "Missing booking payment reference.",
        )

    client = get_stripe_client()
    expected = expected_metadata(checkout, appointment)

    def validate_intent(intent):
        metadata = intent.get("metadata") or {}

        if (
            intent.get("id") != intent_id
            or intent.get("livemode") is not False
            or intent.get("currency") != "myr"
            or intent.get("amount") != checkout.amount_cents
            or payment.gateway_reference not in (None, intent_id)
            or any(
                metadata.get(key) != value
                for key, value in expected.items()
            )
        ):
            raise HTTPException(
                409,
                "The unpaid booking payment needs reconciliation.",
            )

    intent = client.v1.payment_intents.retrieve(
        intent_id
    ).to_dict()

    validate_intent(intent)

    # A failed payment must be made permanently unpayable
    # before its reserved slot can be released.
    if (
        intent.get("status") == "requires_payment_method"
        and intent.get("amount_received") == 0
    ):
        try:
            intent = client.v1.payment_intents.cancel(
                intent_id,
                options={
                    "idempotency_key": (
                        f"booking-close:{checkout.idempotency_key}"
                    ),
                },
            ).to_dict()

        except StripeError:
            # Cancellation may have raced with payment.
            # Retrieve the current state before deciding.
            intent = client.v1.payment_intents.retrieve(
                intent_id
            ).to_dict()

        validate_intent(intent)

    if (
        intent.get("status") == "canceled"
        and intent.get("amount_received") == 0
    ):
        close_expired_booking(
            db,
            context,
            payment,
            checkout,
        )

        if checkout.session_status == "expired":
            checkout.session_status = "failed"

            if payment.payment_status == "expired":
                payment.payment_status = "failed"

        return

    if intent.get("status") not in {
        "succeeded",
        "processing",
        "requires_action",
        "requires_confirmation",
        "requires_capture",
        "requires_payment_method",
    }:
        raise HTTPException(
            409,
            "Unexpected booking payment-intent state.",
        )

    # Keep the reservation while the bank payment is unresolved.
    # If the intent just succeeded, the next pass retrieves
    # the latest checkout and records its verified payment.
    checkout.session_status = "processing"
    checkout.checkout_url = None

def sync_booking_checkout(db, checkout_id):
    try:
        appointment_id = db.scalar(
            select(BookingStripeSession.appointment_id)
            .where(
                BookingStripeSession.booking_checkout_id
                == checkout_id,
            )
        )

        if appointment_id is None:
            raise HTTPException(404, "Booking checkout not found.")

        context = lock_booking_payment_context(
            db,
            appointment_id,
        )

        appointment = context[4]
        payments = context[5]
        checkouts = context[6]

        checkout = next(
            (
                item
                for item in checkouts
                if item.booking_checkout_id == checkout_id
            ),
            None,
        )

        if checkout is None:
            raise HTTPException(409, "Booking checkout changed.")

        payment = next(
            (
                item
                for item in payments
                if item.payment_id == checkout.payment_id
            ),
            None,
        )

        if payment is None:
            raise HTTPException(409, "Linked deposit unavailable.")

        remote = resolve_remote_session(checkout)

        validate_booking_session(
            remote,
            checkout,
            payment,
            appointment,
        )

        deadline = appointment.payment_expires_at

        if (
            appointment.status == "pending_payment"
            and payment.payment_status == "pending"
            and deadline is not None
            and deadline <= utc_now()
            and remote.get("status") == "open"
            and remote.get("payment_status") == "unpaid"
        ):
            client = get_stripe_client()

            try:
                remote = client.v1.checkout.sessions.expire(
                    checkout.stripe_session_id
                ).to_dict()

            except StripeError:
                # Payment may have completed during expiry.
                remote = client.v1.checkout.sessions.retrieve(
                    checkout.stripe_session_id
                ).to_dict()

            validate_booking_session(
                remote,
                checkout,
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
            record_verified_deposit(
                db,
                context,
                payment,
                checkout,
                remote,
            )

        elif status == "expired" and payment_status == "unpaid":
            close_expired_booking(
                db,
                context,
                payment,
                checkout,
            )

        elif status == "open" and payment_status == "unpaid":
            if (
                appointment.status == "pending_payment"
                and payment.payment_status == "pending"
            ):
                checkout.session_status = "open"
            else:
                mark_for_review(checkout, appointment)

        elif status == "complete" and payment_status == "unpaid":
            if payment.payment_status == "pending":
                inspect_unpaid_checkout(
                    db,
                    context,
                    payment,
                    checkout,
                    remote,
                )
            else:
                mark_for_review(checkout, appointment)

        else:
            raise HTTPException(
                409,
                "Unexpected Stripe booking-payment state.",
            )

        result = {
            "appointment_id": appointment.appointment_id,
            "appointment_status": appointment.status,
            "payment_status": payment.payment_status,
            "checkout_status": checkout.session_status,
        }

        db.commit()
        return result

    except StripeError:
        db.rollback()
        raise HTTPException(
            503,
            "Cannot check the booking deposit yet.",
        ) from None

    except Exception:
        db.rollback()
        raise