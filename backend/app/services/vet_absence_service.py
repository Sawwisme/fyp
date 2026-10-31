from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinic_time import CLINIC_TIMEZONE
from app.models import (
    AbsenceAffectedAppointment,
    Appointment,
    Clinic,
    Schedule,
    TimeSlot,
    User,
    Veterinarian,
    VeterinarianAbsence,
)
from app.schemas.vet_absences import VetAbsenceCreate
from app.services.vet_profile_service import get_profile


def reject_vet_absence(
    db: Session,
    veterinarian_id: int,
    appointment_date,
    start_time,
    end_time,
):
    absence_id = db.scalar(
        select(VeterinarianAbsence.absence_id)
        .where(
            VeterinarianAbsence.veterinarian_id == veterinarian_id,
            VeterinarianAbsence.absence_date == appointment_date,
            VeterinarianAbsence.status == "active",
            VeterinarianAbsence.start_time < end_time,
            VeterinarianAbsence.end_time > start_time,
        )
        .limit(1)
    )

    if absence_id is not None:
        raise HTTPException(
            409,
            "The veterinarian is unavailable during this time. "
            "Choose another slot.",
        )


def create_absence(
    db: Session,
    current_user: User,
    data: VetAbsenceCreate,
):
    try:
        profile = get_profile(db, current_user)

        # Match appointment booking's lock order.
        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == profile.clinic_id,
                Clinic.status == "active",
            )
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(403, "Your clinic is unavailable.")

        veterinarian = db.scalar(
            select(Veterinarian)
            .where(
                Veterinarian.veterinarian_id
                == profile.veterinarian_id,
                Veterinarian.clinic_id == clinic.clinic_id,
                Veterinarian.approval_status == "approved",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if veterinarian is None:
            raise HTTPException(403, "Veterinarian unavailable.")

        end = datetime.combine(
            data.absence_date,
            data.end_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        if end <= datetime.now(CLINIC_TIMEZONE):
            raise HTTPException(
                422,
                "The absence period must not have already ended.",
            )

        # Prevent overlapping absence reports.
        reject_vet_absence(
            db,
            veterinarian.veterinarian_id,
            data.absence_date,
            data.start_time,
            data.end_time,
        )

        appointments = db.scalars(
            select(Appointment)
            .join(
                TimeSlot,
                TimeSlot.time_slot_id == Appointment.time_slot_id,
            )
            .join(
                Schedule,
                Schedule.schedule_id == TimeSlot.schedule_id,
            )
            .where(
                Schedule.veterinarian_id
                == veterinarian.veterinarian_id,
                Schedule.schedule_date == data.absence_date,
                TimeSlot.start_time < data.end_time,
                TimeSlot.end_time > data.start_time,
                Appointment.status.in_(
                    ["pending", "confirmed", "in_progress"]
                ),
            )
            .with_for_update()
        ).all()

        if any(
            appointment.status == "in_progress"
            for appointment in appointments
        ):
            raise HTTPException(
                409,
                "A consultation is already in progress during this "
                "period. Arrange its handover before reporting absence.",
            )

        absence = VeterinarianAbsence(
            clinic_id=clinic.clinic_id,
            veterinarian_id=veterinarian.veterinarian_id,
            absence_date=data.absence_date,
            start_time=data.start_time,
            end_time=data.end_time,
            reason=data.reason,
            status="active",
            created_by_user_id=current_user.user_id,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        db.add(absence)
        db.flush()

        for appointment in appointments:
            db.add(
                AbsenceAffectedAppointment(
                    absence_id=absence.absence_id,
                    appointment_id=appointment.appointment_id,
                    original_time_slot_id=appointment.time_slot_id,
                    resolution_status="pending",
                )
            )

        result = {
            "absence_id": absence.absence_id,
            "affected_appointments": len(appointments),
        }

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise

def reject_absent_slots(db: Session, slot_ids: list[int]):
    periods = db.execute(
        select(
            Schedule.veterinarian_id,
            Schedule.schedule_date,
            TimeSlot.start_time,
            TimeSlot.end_time,
        )
        .select_from(TimeSlot)
        .join(
            Schedule,
            Schedule.schedule_id == TimeSlot.schedule_id,
        )
        .where(TimeSlot.time_slot_id.in_(slot_ids))
    ).all()

    for period in periods:
        reject_vet_absence(
            db,
            period.veterinarian_id,
            period.schedule_date,
            period.start_time,
            period.end_time,
        )

def get_rearrangement_ids(
    db: Session,
    appointment_ids: list[int],
) -> set[int]:
    if not appointment_ids:
        return set()

    return set(
        db.scalars(
            select(AbsenceAffectedAppointment.appointment_id)
            .join(
                VeterinarianAbsence,
                VeterinarianAbsence.absence_id
                == AbsenceAffectedAppointment.absence_id,
            )
            .join(
                Appointment,
                Appointment.appointment_id
                == AbsenceAffectedAppointment.appointment_id,
            )
            .where(
                Appointment.appointment_id.in_(appointment_ids),
                Appointment.status.in_(["pending", "confirmed"]),
                Appointment.time_slot_id
                == AbsenceAffectedAppointment.original_time_slot_id,
                Appointment.veterinarian_id
                == VeterinarianAbsence.veterinarian_id,
                VeterinarianAbsence.status == "active",
                AbsenceAffectedAppointment.resolution_status == "pending",
            )
        ).all()
    )

def list_my_absences(
    db: Session,
    current_user: User,
    offset: int,
    limit: int,
):
    veterinarian = get_profile(db, current_user)

    return db.scalars(
        select(VeterinarianAbsence)
        .where(
            VeterinarianAbsence.veterinarian_id
            == veterinarian.veterinarian_id,
            VeterinarianAbsence.clinic_id == veterinarian.clinic_id,
        )
        .order_by(
            VeterinarianAbsence.absence_date.desc(),
            VeterinarianAbsence.start_time.desc(),
            VeterinarianAbsence.absence_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()