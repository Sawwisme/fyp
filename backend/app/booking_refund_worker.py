import logging

from fastapi import HTTPException
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Payment, Refund, Transaction
from app.services.booking_excess_refund_service import (
    process_booking_excess_refund,
)
from app.services.booking_refund_service import (
    process_booking_refund,
)


logger = logging.getLogger(__name__)

PROCESSORS = {
    "booking_cancellation": process_booking_refund,
    "booking_excess": process_booking_excess_refund,
}


def run_pass(stop_event, after_id):
    with SessionLocal() as db:
        requests = db.execute(
            select(
                Refund.refund_id,
                Refund.refund_purpose,
            )
            .join(
                Transaction,
                Transaction.transaction_id == Refund.transaction_id,
            )
            .join(
                Payment,
                Payment.payment_id == Transaction.payment_id,
            )
            .where(
                Refund.refund_id > after_id,
                Refund.status.in_([
                    "approved",
                    "processing",
                    "requires_action",
                ]),
                Refund.refund_purpose.in_(list(PROCESSORS)),
                Transaction.transaction_type == "payment",
                Transaction.order_id.is_(None),
                Payment.order_id.is_(None),
                Payment.appointment_id.is_not(None),
                Payment.payment_purpose == "booking_deposit",
                Payment.payment_method == "online_banking",
            )
            .order_by(Refund.refund_id)
            .limit(10)
        ).all()

    if not requests:
        return 0

    for refund_id, purpose in requests:
        if stop_event.is_set():
            return after_id

        try:
            processor = PROCESSORS[purpose]

            with SessionLocal() as db:
                result = processor(db, refund_id)

                if result["refund_status"] == "failed":
                    logger.warning(
                        "Booking refund %s failed and needs review",
                        refund_id,
                    )

        except HTTPException as exc:
            logger.warning(
                "Booking refund %s deferred (HTTP %s)",
                refund_id,
                exc.status_code,
            )

        except Exception:
            logger.exception(
                "Could not process booking refund %s",
                refund_id,
            )

        after_id = refund_id

    return after_id


def run_worker(stop_event):
    after_id = 0

    while not stop_event.is_set():
        try:
            after_id = run_pass(stop_event, after_id)

        except Exception:
            logger.exception(
                "Booking refund status check failed"
            )

        stop_event.wait(30)