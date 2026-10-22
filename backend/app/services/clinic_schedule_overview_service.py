from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from app.clinic_time import CLINIC_TIMEZONE
from app.models import (
    Appointment,
    PetOwner,
    Schedule,
    TimeSlot,
    User,
    Veterinarian,
)
from app.services.admin_profile_service import get_admin_record


def get_overview(
    db: Session,
    current_user: User,
    schedule_date: date,
    veterinarian_id: int | None,
):
    administrator = get_admin_record(db, current_user)

    vet_query = (
        select(Veterinarian)
        .join(Veterinarian.user)
        .where(
            Veterinarian.clinic_id == administrator.clinic_id,
            User.role == "veterinarian",
        )
        .options(selectinload(Veterinarian.user))
        .order_by(User.full_name, Veterinarian.veterinarian_id)
    )

    if veterinarian_id is not None:
        vet_query = vet_query.where(
            Veterinarian.veterinarian_id == veterinarian_id
        )

    vets = list(db.scalars(vet_query).all())

    if veterinarian_id is not None and not vets:
        raise HTTPException(
            status_code=404,
            detail="Veterinarian not found in your clinic.",
        )

    vet_ids = [vet.veterinarian_id for vet in vets]

    schedules = list(
        db.scalars(
            select(Schedule)
            .where(
                Schedule.veterinarian_id.in_(vet_ids),
                Schedule.schedule_date == schedule_date,
            )
            .options(selectinload(Schedule.time_slots))
            .order_by(
                Schedule.veterinarian_id,
                Schedule.start_time,
                Schedule.schedule_id,
            )
        ).all()
    )

    schedule_ids = [
        schedule.schedule_id for schedule in schedules
    ]

    appointments = list(
        db.scalars(
            select(Appointment)
            .join(
                TimeSlot,
                TimeSlot.time_slot_id == Appointment.time_slot_id,
            )
            .where(TimeSlot.schedule_id.in_(schedule_ids))
            .options(
                selectinload(Appointment.pet),
                selectinload(Appointment.owner)
                .selectinload(PetOwner.user),
            )
            .order_by(Appointment.appointment_id)
        ).all()
    )

    appointments_by_slot = {}

    for appointment in appointments:
        owner = appointment.owner
        account = owner.user

        record = {
            "appointment_id": appointment.appointment_id,
            "pet_owner_id": appointment.pet_owner_id,
            "pet_id": appointment.pet_id,
            "owner_name": (
                account.full_name
                if account is not None
                else owner.contact_name
            ),
            "pet_name": appointment.pet.pet_name,
            "appointment_type": appointment.appointment_type,
            "appointment_source": appointment.appointment_source,
            "status": appointment.status,
        }

        appointments_by_slot.setdefault(
            appointment.time_slot_id,
            [],
        ).append(record)

    schedules_by_vet = {}

    for schedule in schedules:
        schedules_by_vet.setdefault(
            schedule.veterinarian_id,
            [],
        ).append(schedule)

    summary = {
        "veterinarians": len(vets),
        "veterinarians_with_schedules": 0,
        "active_schedules": 0,
        "appointments": 0,
        "walk_in_appointments": 0,
        "available_slots": 0,
        "blocked_slots": 0,
    }

    now = datetime.now(CLINIC_TIMEZONE)
    rows = []

    for vet in vets:
        eligible = (
            vet.user.status == "active"
            and vet.approval_status == "approved"
        )

        row = {
            "veterinarian_id": vet.veterinarian_id,
            "full_name": vet.user.full_name,
            "account_status": vet.user.status,
            "approval_status": vet.approval_status,
            "appointment_count": 0,
            "available_slots": 0,
            "blocked_slots": 0,
            "schedules": [],
        }

        has_active_schedule = False

        for schedule in schedules_by_vet.get(
            vet.veterinarian_id,
            [],
        ):
            active = schedule.status == "active"

            if active:
                has_active_schedule = True
                summary["active_schedules"] += 1

            schedule_row = {
                "schedule_id": schedule.schedule_id,
                "schedule_date": schedule.schedule_date,
                "start_time": schedule.start_time,
                "end_time": schedule.end_time,
                "status": schedule.status,
                "time_slots": [],
            }

            for slot in sorted(
                schedule.time_slots,
                key=lambda item: (item.start_time, item.time_slot_id),
            ):
                records = appointments_by_slot.get(
                    slot.time_slot_id,
                    [],
                )

                occupying = [
                    record for record in records
                    if record["status"] not in {"cancelled", "rejected"}
                ]

                start = datetime.combine(
                    schedule_date,
                    slot.start_time,
                    tzinfo=CLINIC_TIMEZONE,
                )
                end = datetime.combine(
                    schedule_date,
                    slot.end_time,
                    tzinfo=CLINIC_TIMEZONE,
                )

                free = (
                    eligible
                    and active
                    and slot.status == "available"
                    and not occupying
                    and end > now
                )

                if free:
                    row["available_slots"] += 1

                if active and slot.status == "blocked" and end > now:
                    row["blocked_slots"] += 1

                row["appointment_count"] += len(occupying)

                summary["walk_in_appointments"] += sum(
                    record["appointment_source"] == "walk_in"
                    for record in occupying
                )

                schedule_row["time_slots"].append({
                    "time_slot_id": slot.time_slot_id,
                    "start_time": slot.start_time,
                    "end_time": slot.end_time,
                    "status": slot.status,
                    "can_book_walk_in": (
                        free and schedule_date == now.date()
                    ),
                    "can_book_reception": free and start > now,
                    "appointments": records,
                })

            row["schedules"].append(schedule_row)

        if has_active_schedule:
            summary["veterinarians_with_schedules"] += 1

        summary["appointments"] += row["appointment_count"]
        summary["available_slots"] += row["available_slots"]
        summary["blocked_slots"] += row["blocked_slots"]

        rows.append(row)

    return {
        "schedule_date": schedule_date,
        "summary": summary,
        "veterinarians": rows,
    }

def get_calendar(
    db: Session,
    current_user: User,
    start_date: date,
    end_date: date,
    veterinarian_id: int | None,
):
    administrator = get_admin_record(db, current_user)

    if end_date < start_date or (end_date - start_date).days > 41:
        raise HTTPException(
            status_code=400,
            detail="Select a calendar range of at most 42 days.",
        )

    statement = (
        select(Schedule)
        .join(Schedule.veterinarian)
        .join(Veterinarian.user)
        .where(
            Veterinarian.clinic_id == administrator.clinic_id,
            User.role == "veterinarian",
            Schedule.schedule_date >= start_date,
            Schedule.schedule_date <= end_date,
            Schedule.status == "active",
        )
        .options(
            selectinload(Schedule.veterinarian)
            .selectinload(Veterinarian.user)
        )
        .order_by(
            Schedule.schedule_date,
            User.full_name,
            Schedule.start_time,
        )
    )

    if veterinarian_id is not None:
        statement = statement.where(
            Schedule.veterinarian_id == veterinarian_id
        )

    schedules = list(db.scalars(statement).all())

    counts = dict(
        db.execute(
            select(
                TimeSlot.schedule_id,
                func.count(Appointment.appointment_id),
            )
            .join(
                Appointment,
                Appointment.time_slot_id == TimeSlot.time_slot_id,
            )
            .where(
                TimeSlot.schedule_id.in_([
                    item.schedule_id for item in schedules
                ]),
                Appointment.status.notin_(["cancelled", "rejected"]),
            )
            .group_by(TimeSlot.schedule_id)
        ).all()
    )

    entries = {}

    for schedule in schedules:
        key = (
            schedule.schedule_date,
            schedule.veterinarian_id,
        )

        if key not in entries:
            entries[key] = {
                "schedule_date": schedule.schedule_date,
                "veterinarian_id": schedule.veterinarian_id,
                "full_name": schedule.veterinarian.user.full_name,
                "periods": [],
                "appointment_count": 0,
            }

        entries[key]["periods"].append({
            "start_time": schedule.start_time,
            "end_time": schedule.end_time,
        })

        entries[key]["appointment_count"] += counts.get(
            schedule.schedule_id,
            0,
        )

    return {"entries": list(entries.values())}