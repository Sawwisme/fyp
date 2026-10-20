from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    Clinic,
    ClinicWorkingHour,
    Schedule,
    User,
    Veterinarian,
)
from app.schemas.clinic_hours import WorkingHoursUpdate
from app.services.admin_profile_service import get_admin_record
from app.clinic_time import CLINIC_TIMEZONE


def fits_working_hours(periods, weekday, start_time, end_time) -> bool:
    # Adjacent opening periods count as continuous working time.
    covered_until = start_time

    matching = sorted(
        (period for period in periods if period.weekday == weekday),
        key=lambda period: period.start_time,
    )

    for period in matching:
        if period.end_time <= covered_until:
            continue

        if period.start_time > covered_until:
            return False

        covered_until = period.end_time

        if covered_until >= end_time:
            return True

    return False


def read_hours(db: Session, clinic_id: int):
    return list(
        db.scalars(
            select(ClinicWorkingHour)
            .where(ClinicWorkingHour.clinic_id == clinic_id)
            .order_by(
                ClinicWorkingHour.weekday,
                ClinicWorkingHour.start_time,
            )
        ).all()
    )


def get_my_hours(db: Session, current_user: User):
    administrator = get_admin_record(db, current_user)

    return read_hours(db, administrator.clinic_id)


def replace_my_hours(
    db: Session,
    current_user: User,
    data: WorkingHoursUpdate,
):
    administrator = get_admin_record(db, current_user)

    try:
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

        now = datetime.now(CLINIC_TIMEZONE)

        schedules = db.scalars(
            select(Schedule)
            .join(Schedule.veterinarian)
            .where(
                Veterinarian.clinic_id == clinic.clinic_id,
                Schedule.status == "active",
                Schedule.schedule_date >= now.date(),
            )
            .with_for_update()
        ).all()

        for schedule in schedules:
            end = datetime.combine(
                schedule.schedule_date,
                schedule.end_time,
                tzinfo=CLINIC_TIMEZONE,
            )

            if end <= now:
                continue

            if not fits_working_hours(
                data.periods,
                schedule.schedule_date.weekday(),
                schedule.start_time,
                schedule.end_time,
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "These hours conflict with an existing active "
                        f"schedule on {schedule.schedule_date}. "
                        "Handle that schedule before changing clinic hours."
                    ),
                )

        db.execute(
            delete(ClinicWorkingHour).where(
                ClinicWorkingHour.clinic_id == clinic.clinic_id
            )
        )

        db.add_all([
            ClinicWorkingHour(
                clinic_id=clinic.clinic_id,
                weekday=period.weekday,
                start_time=period.start_time,
                end_time=period.end_time,
            )
            for period in data.periods
        ])

        db.commit()
    except Exception:
        db.rollback()
        raise

    return read_hours(db, administrator.clinic_id)