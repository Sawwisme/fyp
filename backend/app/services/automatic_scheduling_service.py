from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinic_time import CLINIC_TIMEZONE
from app.models import (
    AutomaticScheduleRule,
    Clinic,
    ClinicWorkingHour,
    Schedule,
    TimeSlot,
    User,
    Veterinarian,
)
from app.schemas.automatic_scheduling import AutomaticSchedulingUpdate
from app.services.admin_profile_service import get_admin_record


def read_rules(db: Session, current_user: User):
    administrator = get_admin_record(db, current_user)

    return list(
        db.scalars(
            select(AutomaticScheduleRule)
            .join(
                Veterinarian,
                Veterinarian.veterinarian_id
                == AutomaticScheduleRule.veterinarian_id,
            )
            .where(
                Veterinarian.clinic_id == administrator.clinic_id
            )
            .order_by(AutomaticScheduleRule.veterinarian_id)
        ).all()
    )


def validate_periods(periods, slot_minutes):
    if not periods:
        raise HTTPException(
            status_code=400,
            detail="Save clinic working hours before enabling automation.",
        )

    previous_end = {}

    for period in sorted(
        periods,
        key=lambda item: (item.weekday, item.start_time),
    ):
        start = period.start_time
        end = period.end_time

        duration = (
            (end.hour * 60 + end.minute)
            - (start.hour * 60 + start.minute)
        )

        if (
            start.second
            or start.microsecond
            or end.second
            or end.microsecond
            or duration <= 0
            or duration % slot_minutes
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Every opening period must divide evenly into "
                    "the selected slot length."
                ),
            )

        if previous_end.get(period.weekday, start) > start:
            raise HTTPException(
                status_code=400,
                detail="Clinic working hours contain overlapping periods.",
            )

        previous_end[period.weekday] = end


def save_rules(
    db: Session,
    current_user: User,
    data: AutomaticSchedulingUpdate,
):
    try:
        administrator = get_admin_record(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == administrator.clinic_id,
                Clinic.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(
                status_code=403,
                detail="Your clinic is not active.",
            )

        vets = list(
            db.scalars(
                select(Veterinarian)
                .join(Veterinarian.user)
                .where(
                    Veterinarian.clinic_id == clinic.clinic_id,
                    Veterinarian.veterinarian_id.in_(
                        data.veterinarian_ids
                    ),
                    User.role == "veterinarian",
                )
                .order_by(Veterinarian.veterinarian_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            ).all()
        )

        if len(vets) != len(data.veterinarian_ids):
            raise HTTPException(
                status_code=400,
                detail="Select veterinarians from your own clinic.",
            )

        if data.enabled:
            for vet in vets:
                if (
                    vet.approval_status != "approved"
                    or vet.user.status != "active"
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Only active, approved veterinarians "
                            "can use automatic scheduling."
                        ),
                    )

            periods = list(
                db.scalars(
                    select(ClinicWorkingHour)
                    .where(
                        ClinicWorkingHour.clinic_id == clinic.clinic_id
                    )
                    .with_for_update()
                ).all()
            )

            validate_periods(periods, data.slot_minutes)

        for vet in vets:
            rule = db.scalar(
                select(AutomaticScheduleRule)
                .where(
                    AutomaticScheduleRule.veterinarian_id
                    == vet.veterinarian_id
                )
                .execution_options(populate_existing=True)
                .with_for_update()
            )

            if rule is None:
                rule = AutomaticScheduleRule(
                    veterinarian_id=vet.veterinarian_id
                )
                db.add(rule)

            rule.enabled = data.enabled
            rule.slot_minutes = data.slot_minutes
            rule.days_ahead = data.days_ahead

            # Request a fresh run after changing settings.
            rule.last_run_at = None
            rule.last_error = None

        db.commit()

    except Exception:
        db.rollback()
        raise

    return read_rules(db, current_user)


def generate_for_rule(db: Session, rule_id: int):
    result = {
        "created_schedules": 0,
        "created_slots": 0,
        "preserved_days": 0,
    }

    try:
        # Find the clinic first so every generation operation
        # takes locks in the same clinic -> vet -> rule order.
        clinic_id = db.scalar(
            select(Veterinarian.clinic_id)
            .join(
                AutomaticScheduleRule,
                AutomaticScheduleRule.veterinarian_id
                == Veterinarian.veterinarian_id,
            )
            .where(
                AutomaticScheduleRule.automatic_schedule_rule_id
                == rule_id
            )
        )

        if clinic_id is None:
            db.rollback()
            return result

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == clinic_id,
                Clinic.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if clinic is None:
            db.rollback()
            return result

        vet = db.scalar(
            select(Veterinarian)
            .join(Veterinarian.user)
            .join(
                AutomaticScheduleRule,
                AutomaticScheduleRule.veterinarian_id
                == Veterinarian.veterinarian_id,
            )
            .where(
                AutomaticScheduleRule.automatic_schedule_rule_id
                == rule_id,
                Veterinarian.clinic_id == clinic_id,
                Veterinarian.approval_status == "approved",
                User.role == "veterinarian",
                User.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if vet is None:
            db.rollback()
            return result

        rule = db.scalar(
            select(AutomaticScheduleRule)
            .where(
                AutomaticScheduleRule.automatic_schedule_rule_id
                == rule_id,
                AutomaticScheduleRule.veterinarian_id
                == vet.veterinarian_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if rule is None or not rule.enabled:
            db.rollback()
            return result

        periods = list(
            db.scalars(
                select(ClinicWorkingHour)
                .where(
                    ClinicWorkingHour.clinic_id == clinic_id
                )
                .order_by(
                    ClinicWorkingHour.weekday,
                    ClinicWorkingHour.start_time,
                )
                .execution_options(populate_existing=True)
                .with_for_update()
            ).all()
        )

        validate_periods(periods, rule.slot_minutes)

        today = datetime.now(CLINIC_TIMEZONE).date()
        first_day = today + timedelta(days=1)
        last_day = today + timedelta(days=rule.days_ahead)

        # Include ALL statuses. Cancelled schedules must not
        # silently become available again.
        existing_days = set(
            db.scalars(
                select(Schedule.schedule_date)
                .where(
                    Schedule.veterinarian_id == vet.veterinarian_id,
                    Schedule.schedule_date >= first_day,
                    Schedule.schedule_date <= last_day,
                )
                .with_for_update()
            ).all()
        )

        periods_by_day = {}

        for period in periods:
            periods_by_day.setdefault(period.weekday, []).append(period)

        pending = []
        day = first_day
        step = timedelta(minutes=rule.slot_minutes)

        while day <= last_day:
            if day in existing_days:
                result["preserved_days"] += 1
                day += timedelta(days=1)
                continue

            for period in periods_by_day.get(day.weekday(), []):
                schedule = Schedule(
                    veterinarian_id=vet.veterinarian_id,
                    schedule_date=day,
                    start_time=period.start_time,
                    end_time=period.end_time,
                    status="active",
                )

                cursor = datetime.combine(day, period.start_time)
                end = datetime.combine(day, period.end_time)

                while cursor < end:
                    slot_end = cursor + step

                    schedule.time_slots.append(
                        TimeSlot(
                            start_time=cursor.time(),
                            end_time=slot_end.time(),
                            status="available",
                        )
                    )

                    result["created_slots"] += 1
                    cursor = slot_end

                pending.append(schedule)

            day += timedelta(days=1)

        db.add_all(pending)

        result["created_schedules"] = len(pending)
        rule.last_run_at = datetime.now(timezone.utc).replace(tzinfo=None)
        rule.last_error = None

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise