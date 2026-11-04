import logging

from fastapi import HTTPException
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Refund, Transaction
from app.schemas.clinic_refunds import OnlineRefundProcess
from app.services.stripe_refund_service import (
    process_online_refund,
)


logger = logging.getLogger(__name__)


def run_pass(stop_event, after_id):
    with SessionLocal() as db:
        requests = db.execute(
            select(
                Refund.refund_id,
                Refund.version,
                Transaction.order_id,
            )
            .join(
                Transaction,
                Transaction.transaction_id
                == Refund.transaction_id,
            )
            .where(
                Refund.refund_id > after_id,
                Refund.status.in_([
                    "processing",
                    "requires_action",
                ]),
                Refund.gateway_idempotency_key.is_not(None),
                Refund.gateway_requested_at.is_not(None),
                Transaction.order_id.is_not(None),
            )
            .order_by(Refund.refund_id)
            .limit(10)
        ).all()

    if not requests:
        return 0

    for refund_id, version, order_id in requests:
        if stop_event.is_set():
            return after_id

        try:
            with SessionLocal() as db:
                process_online_refund(
                    db=db,
                    current_user=None,
                    order_id=order_id,
                    refund_id=refund_id,
                    data=OnlineRefundProcess(
                        expected_version=version,
                    ),
                )

        except HTTPException as exc:
            logger.warning(
                "Refund %s sync deferred (HTTP %s)",
                refund_id,
                exc.status_code,
            )

        except Exception:
            logger.exception(
                "Could not sync Stripe refund %s",
                refund_id,
            )

        after_id = refund_id

    # Scan later requests before returning to earlier ones.
    return after_id


def run_worker(stop_event):
    after_id = 0

    while not stop_event.is_set():
        try:
            after_id = run_pass(
                stop_event,
                after_id,
            )

        except Exception:
            logger.exception(
                "Stripe refund status check failed"
            )

        stop_event.wait(30)