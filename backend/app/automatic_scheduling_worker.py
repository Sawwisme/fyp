import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.clinic_time import CLINIC_TIMEZONE
from app.database import SessionLocal
from app.models import AutomaticScheduleRule
from app.services.automatic_scheduling_service import generate_for_rule


logger = logging.getLogger(__name__)


def should_run(last_run_at, last_error, force=False):
    if force or last_run_at is None:
        return True

    last_run = last_run_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    # Retry failed generation after one hour.
    if last_error:
        return now - last_run >= timedelta(hours=1)

    return (
        last_run.astimezone(CLINIC_TIMEZONE).date()
        < now.astimezone(CLINIC_TIMEZONE).date()
    )


def record_failure(rule_id, previous_run, slot_minutes, days_ahead, error):
    with SessionLocal() as db:
        try:
            rule = db.scalar(
                select(AutomaticScheduleRule)
                .where(
                    AutomaticScheduleRule.automatic_schedule_rule_id
                    == rule_id
                )
                .execution_options(populate_existing=True)
                .with_for_update()
            )

            # Do not overwrite settings changed during this attempt.
            if (
                rule is None
                or not rule.enabled
                or rule.slot_minutes != slot_minutes
                or rule.days_ahead != days_ahead
                or rule.last_run_at != previous_run
            ):
                db.rollback()
                return

            rule.last_run_at = datetime.now(timezone.utc).replace(
                tzinfo=None
            )

            rule.last_error = (
                str(error.detail)[:1000]
                if isinstance(error, HTTPException)
                else "Automatic generation failed. Check the backend."
            )

            db.commit()

        except Exception:
            db.rollback()
            logger.error(
                "Could not save automatic scheduling error for rule %s",
                rule_id,
            )


def run_pass(stop_event, force=False):
    with SessionLocal() as db:
        rows = db.execute(
            select(
                AutomaticScheduleRule.automatic_schedule_rule_id,
                AutomaticScheduleRule.last_run_at,
                AutomaticScheduleRule.last_error,
                AutomaticScheduleRule.slot_minutes,
                AutomaticScheduleRule.days_ahead,
            )
            .where(AutomaticScheduleRule.enabled.is_(True))
            .order_by(
                AutomaticScheduleRule.automatic_schedule_rule_id
            )
        ).all()

    for rule_id, last_run, last_error, slot_minutes, days_ahead in rows:
        if stop_event.is_set():
            return

        if not should_run(last_run, last_error, force):
            continue

        try:
            with SessionLocal() as db:
                result = generate_for_rule(db, rule_id)

            if result["created_schedules"]:
                logger.info(
                    "Automatic scheduling rule %s created "
                    "%s schedules and %s slots",
                    rule_id,
                    result["created_schedules"],
                    result["created_slots"],
                )

        except Exception as error:
            logger.error(
                "Automatic scheduling rule %s failed (%s)",
                rule_id,
                type(error).__name__,
            )

            record_failure(
                rule_id,
                last_run,
                slot_minutes,
                days_ahead,
                error,
            )


def run_worker(stop_event):
    force = True

    while not stop_event.is_set():
        try:
            run_pass(stop_event, force=force)

        except Exception as error:
            logger.error(
                "Automatic scheduling check failed (%s)",
                type(error).__name__,
            )

        force = False

        # Wait without preventing backend shutdown.
        stop_event.wait(60)