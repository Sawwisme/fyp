from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinic_time import CLINIC_TIMEZONE
from app.models import (
    Clinic,
    ClinicWorkingHour,
    Schedule,
    TimeSlot,
    User,
    Veterinarian,
)
from app.schemas.schedule import BulkScheduleCreate
from app.services.admin_profile_service import get_admin_record


def generate_schedules(
    db: Session,
    current_user: User,
    data: BulkScheduleCreate,
) -> dict:
    try:
        administrator = get_admin_record(db, current_user)

        today = datetime.now(CLINIC_TIMEZONE).date()

        if data.start_date <= today:
            raise HTTPException(
                status_code=400,
                detail="Bulk generation must start tomorrow or later.",
            )

        # Use the same clinic lock as working-hour edits
        # and individual schedule creation.
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

        periods = list(
            db.scalars(
                select(ClinicWorkingHour)
                .where(
                    ClinicWorkingHour.clinic_id == clinic.clinic_id
                )
                .order_by(
                    ClinicWorkingHour.weekday,
                    ClinicWorkingHour.start_time,
                )
                .execution_options(populate_existing=True)
                .with_for_update()
            ).all()
        )

        if not periods:
            raise HTTPException(
                status_code=400,
                detail="Set clinic working hours before generating schedules.",
            )

        veterinarians = list(
            db.scalars(
                select(Veterinarian)
                .join(Veterinarian.user)
                .where(
                    Veterinarian.veterinarian_id.in_(
                        data.veterinarian_ids
                    ),
                    Veterinarian.clinic_id == clinic.clinic_id,
                    Veterinarian.approval_status == "approved",
                    User.role == "veterinarian",
                    User.status == "active",
                )
                .order_by(Veterinarian.veterinarian_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            ).all()
        )

        if len(veterinarians) != len(data.veterinarian_ids):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Select only active, approved veterinarians "
                    "from your clinic."
                ),
            )

        existing = list(
            db.scalars(
                select(Schedule)
                .where(
                    Schedule.veterinarian_id.in_(
                        data.veterinarian_ids
                    ),
                    Schedule.schedule_date >= data.start_date,
                    Schedule.schedule_date <= data.end_date,
                    Schedule.status == "active",
                )
                .execution_options(populate_existing=True)
                .with_for_update()
            ).all()
        )

        periods_by_day = {}

        for period in periods:
            periods_by_day.setdefault(period.weekday, []).append(period)

        existing_by_day = {}

        for schedule in existing:
            key = (
                schedule.veterinarian_id,
                schedule.schedule_date,
            )
            existing_by_day.setdefault(key, []).append(schedule)

        pending = []
        slot_count = 0
        closed_days = 0
        day = data.start_date

        while day <= data.end_date:
            day_periods = periods_by_day.get(day.weekday(), [])

            if not day_periods:
                closed_days += 1
                day += timedelta(days=1)
                continue

            for period in day_periods:
                start = datetime.combine(day, period.start_time)
                end = datetime.combine(day, period.end_time)

                duration = int((end - start).total_seconds())

                if (
                    duration <= 0
                    or start.second
                    or start.microsecond
                    or end.second
                    or end.microsecond
                    or duration % (data.slot_minutes * 60)
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Clinic hours on {day.isoformat()} "
                            "do not divide evenly into the selected "
                            "slot duration. Choose another slot duration."
                        ),
                    )

                slots_per_schedule = duration // (
                    data.slot_minutes * 60
                )

                for veterinarian in veterinarians:
                    key = (
                        veterinarian.veterinarian_id,
                        day,
                    )

                    overlaps = any(
                        schedule.start_time < period.end_time
                        and schedule.end_time > period.start_time
                        for schedule in existing_by_day.get(key, [])
                    )

                    if overlaps:
                        raise HTTPException(
                            status_code=409,
                            detail=(
                                f"Veterinarian "
                                f"{veterinarian.veterinarian_id} "
                                f"already has a schedule on "
                                f"{day.isoformat()} during these hours. "
                                "Nothing was created. Adjust the vets "
                                "or date range."
                            ),
                        )

                    slot_count += slots_per_schedule

                    if slot_count > 10000:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "This would create more than 10,000 slots. "
                                "Select fewer vets or a shorter date range."
                            ),
                        )

                    schedule = Schedule(
                        veterinarian_id=veterinarian.veterinarian_id,
                        schedule_date=day,
                        start_time=period.start_time,
                        end_time=period.end_time,
                        status="active",
                    )

                    cursor = start
                    step = timedelta(minutes=data.slot_minutes)

                    while cursor < end:
                        slot_end = cursor + step

                        schedule.time_slots.append(
                            TimeSlot(
                                start_time=cursor.time(),
                                end_time=slot_end.time(),
                                status="available",
                            )
                        )

                        cursor = slot_end

                    pending.append(schedule)

            day += timedelta(days=1)

        if not pending:
            raise HTTPException(
                status_code=400,
                detail="The selected date range contains only closed days.",
            )

        db.add_all(pending)
        db.commit()

        return {
            "created_schedules": len(pending),
            "created_slots": slot_count,
            "closed_days": closed_days,
        }

    except Exception:
        db.rollback()
        raise