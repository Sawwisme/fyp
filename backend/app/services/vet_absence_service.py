from datetime import date, datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

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
    PetOwner,
)
from app.schemas.vet_absences import (
    VetAbsenceCreate,
    RearrangementResolve,
)
from app.services.notification_service import notify_absence_reported
from app.services.vet_profile_service import get_profile
from app.services.admin_profile_service import get_admin_record


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

        notify_absence_reported(
            db,
            absence,
            current_user.full_name,
            appointments,
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

def list_clinic_rearrangements(
    db: Session,
    current_user: User,
    pending_only: bool,
    offset: int,
    limit: int,
):
    administrator = get_admin_record(db, current_user)

    statement = (
        select(
            AbsenceAffectedAppointment,
            VeterinarianAbsence,
            Appointment,
            User.full_name.label("absent_vet_name"),
            TimeSlot.start_time.label("original_start_time"),
            TimeSlot.end_time.label("original_end_time"),
        )
        .select_from(AbsenceAffectedAppointment)
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
        .join(
            Veterinarian,
            Veterinarian.veterinarian_id
            == VeterinarianAbsence.veterinarian_id,
        )
        .join(
            User,
            User.user_id == Veterinarian.user_id,
        )
        .join(
            TimeSlot,
            TimeSlot.time_slot_id
            == AbsenceAffectedAppointment.original_time_slot_id,
        )
        .options(
            selectinload(Appointment.pet),
            selectinload(Appointment.owner).selectinload(
                PetOwner.user
            ),
            selectinload(Appointment.time_slot),
            selectinload(Appointment.veterinarian).selectinload(
                Veterinarian.user
            ),
        )
        .where(
            VeterinarianAbsence.clinic_id
            == administrator.clinic_id,
        )
    )

    if pending_only:
        statement = statement.where(
            AbsenceAffectedAppointment.resolution_status == "pending",
        )

    records = db.execute(
        statement
        .order_by(
            VeterinarianAbsence.absence_date,
            TimeSlot.start_time,
            AbsenceAffectedAppointment.affected_id,
        )
        .offset(offset)
        .limit(limit)
    ).all()

    result = []

    for affected, absence, appointment, vet_name, start, end in records:
        owner = appointment.owner
        owner_user = owner.user
        current_slot = appointment.time_slot

        result.append({
            "affected_id": affected.affected_id,
            "absence_id": absence.absence_id,
            "appointment_id": appointment.appointment_id,
            "current_time_slot_id": appointment.time_slot_id,
                        "current_veterinarian_id": appointment.veterinarian_id,
            "current_vet_name": (
                appointment.veterinarian.user.full_name
                if appointment.veterinarian is not None
                else vet_name
            ),
            "can_rearrange": (
                appointment.status in ("pending", "confirmed")
                and datetime.combine(
                    appointment.appointment_date,
                    current_slot.start_time,
                    tzinfo=CLINIC_TIMEZONE,
                ) > datetime.now(CLINIC_TIMEZONE)
            ),
            "pet_name": appointment.pet.pet_name,
            "owner_name": (
                owner_user.full_name
                if owner_user is not None
                else owner.contact_name
            ),
            "owner_phone": (
                owner_user.phone_number
                if owner_user is not None
                else owner.contact_phone
            ),
            "absent_vet_name": vet_name,
            "absence_reason": absence.reason,
            "original_date": absence.absence_date,
            "original_start_time": start,
            "original_end_time": end,
            "current_date": appointment.appointment_date,
            "current_start_time": current_slot.start_time,
            "current_end_time": current_slot.end_time,
            "appointment_status": appointment.status,
            "booking_changed": (
                appointment.time_slot_id
                != affected.original_time_slot_id
            ),
            "resolution_status": affected.resolution_status,
            "resolution_note": affected.resolution_note,
            "owner_agreement_note": affected.owner_agreement_note,
            "resolved_at": affected.resolved_at,
        })

    return result

def resolve_rearrangement(
    db: Session,
    current_user: User,
    affected_id: int,
    data: RearrangementResolve,
):
    try:
        administrator = get_admin_record(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == administrator.clinic_id,
                Clinic.status == "active",
            )
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(403, "Your clinic is unavailable.")

        record = db.execute(
            select(
                AbsenceAffectedAppointment,
                VeterinarianAbsence,
            )
            .join(
                VeterinarianAbsence,
                VeterinarianAbsence.absence_id
                == AbsenceAffectedAppointment.absence_id,
            )
            .where(
                AbsenceAffectedAppointment.affected_id == affected_id,
                VeterinarianAbsence.clinic_id == clinic.clinic_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        ).first()

        if record is None:
            raise HTTPException(404, "Rearrangement record not found.")

        affected, absence = record

        if affected.resolution_status != "pending":
            raise HTTPException(
                409,
                "This rearrangement has already been resolved.",
            )

        appointment = db.scalar(
            select(Appointment)
            .where(
                Appointment.appointment_id
                == affected.appointment_id
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if appointment is None:
            raise HTTPException(404, "Appointment not found.")

        if (
            appointment.time_slot_id != data.expected_time_slot_id
            or appointment.status
            != data.expected_appointment_status
        ):
            raise HTTPException(
                409,
                "The appointment changed. Refresh before recording "
                "its resolution.",
            )

        if appointment.status in ("cancelled", "rejected"):
            resolution = "cancelled"

        elif appointment.time_slot_id != affected.original_time_slot_id:
            resolution = (
                "reassigned"
                if appointment.veterinarian_id
                != absence.veterinarian_id
                else "rescheduled"
            )

        elif absence.status == "cancelled":
            resolution = "no_change"

        else:
            raise HTTPException(
                409,
                "Move or cancel the appointment first. "
                "It is still assigned to the original affected slot.",
            )

        affected.resolution_status = resolution
        affected.resolution_note = data.resolution_note
        affected.owner_agreement_note = data.owner_agreement_note
        affected.resolved_by_user_id = current_user.user_id
        affected.resolved_at = datetime.now(
            timezone.utc
        ).replace(tzinfo=None)

        result = {
            "affected_id": affected.affected_id,
            "resolution_status": resolution,
            "message": "Rearrangement resolution recorded.",
        }

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise

def list_my_absence_periods(
    db: Session,
    current_user: User,
    start_date: date,
    end_date: date,
):
    veterinarian = get_profile(db, current_user)

    if end_date < start_date or (end_date - start_date).days >= 42:
        raise HTTPException(
            422,
            "Choose a date range of up to 42 days.",
        )

    return db.scalars(
        select(VeterinarianAbsence)
        .where(
            VeterinarianAbsence.veterinarian_id
            == veterinarian.veterinarian_id,
            VeterinarianAbsence.clinic_id == veterinarian.clinic_id,
            VeterinarianAbsence.status == "active",
            VeterinarianAbsence.absence_date >= start_date,
            VeterinarianAbsence.absence_date <= end_date,
        )
        .order_by(
            VeterinarianAbsence.absence_date,
            VeterinarianAbsence.start_time,
        )
    ).all()

def withdraw_my_absence(
    db: Session,
    current_user: User,
    absence_id: int,
):
    try:
        profile = get_profile(db, current_user)

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
            .with_for_update()
        )

        if veterinarian is None:
            raise HTTPException(403, "Veterinarian unavailable.")

        absence = db.scalar(
            select(VeterinarianAbsence)
            .where(
                VeterinarianAbsence.absence_id == absence_id,
                VeterinarianAbsence.veterinarian_id
                == veterinarian.veterinarian_id,
                VeterinarianAbsence.clinic_id == clinic.clinic_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if absence is None:
            raise HTTPException(404, "Absence report not found.")

        if absence.status != "active":
            raise HTTPException(
                409,
                "This absence report has already been withdrawn.",
            )

        affected_records = db.scalars(
            select(AbsenceAffectedAppointment)
            .where(
                AbsenceAffectedAppointment.absence_id == absence_id,
                AbsenceAffectedAppointment.resolution_status
                == "pending",
            )
            .order_by(AbsenceAffectedAppointment.affected_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        ).all()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        unchanged_count = 0

        for affected in affected_records:
            appointment = db.scalar(
                select(Appointment)
                .where(
                    Appointment.appointment_id
                    == affected.appointment_id
                )
                .execution_options(populate_existing=True)
                .with_for_update()
            )

            if appointment is None:
                continue

            # Preserve bookings already moved to another slot.
            if (
                appointment.time_slot_id
                != affected.original_time_slot_id
                or appointment.veterinarian_id
                != veterinarian.veterinarian_id
            ):
                continue

            # Existing cancellations still need their resolution record.
            if appointment.status not in ("pending", "confirmed"):
                continue

            affected.resolution_status = "no_change"
            affected.resolution_note = (
                "Veterinarian withdrew the absence report. "
                "The original appointment remains unchanged."
            )
            affected.resolved_by_user_id = current_user.user_id
            affected.resolved_at = now
            unchanged_count += 1

        absence.status = "cancelled"
        absence.cancelled_at = now

        result = {
            "absence_id": absence.absence_id,
            "status": "cancelled",
            "unchanged_appointments": unchanged_count,
            "message": "Absence report withdrawn.",
        }

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise