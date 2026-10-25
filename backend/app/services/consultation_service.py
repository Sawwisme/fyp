from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.clinic_time import CLINIC_TIMEZONE
from app.models import (
    Appointment,
    Clinic,
    Consultation,
    Pet,
    PetOwner,
    Prescription,
    Schedule,
    TimeSlot,
    Treatment,
    User,
)
from app.schemas.consultations import ConsultationSave
from app.services.schedule_service import lock_schedule
from app.services.vet_profile_service import get_profile


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _details_statement(veterinarian):
    return (
        select(Consultation)
        .where(
            Consultation.veterinarian_id
            == veterinarian.veterinarian_id,
            Consultation.clinic_id == veterinarian.clinic_id,
        )
        .options(
            selectinload(Consultation.pet),
            selectinload(Consultation.appointment)
            .selectinload(Appointment.owner)
            .selectinload(PetOwner.user),
            selectinload(Consultation.appointment)
            .selectinload(Appointment.emergency_request),
            selectinload(Consultation.treatments),
            selectinload(Consultation.prescriptions),
        )
        .execution_options(populate_existing=True)
    )


def _serialize(record):
    owner = record.appointment.owner
    emergency = record.appointment.emergency_request

    return {
        "consultation_id": record.consultation_id,
        "appointment_id": record.appointment_id,
        "clinic_id": record.clinic_id,
        "pet_id": record.pet_id,
        "veterinarian_id": record.veterinarian_id,
        "pet_name": record.pet.pet_name,
        "owner_name": (
            owner.user.full_name
            if owner.user is not None
            else owner.contact_name or "Not recorded"
        ),
        "consultation_date": record.consultation_date,
        "consultation_information": record.consultation_information,
        "examination_findings": record.examination_findings,
        "diagnosis": record.diagnosis,
        "notes": record.notes,
        "status": record.status,
        "version": record.version,
        "completed_at": record.completed_at,
        "updated_at": record.updated_at,
        "emergency_reason": (
            emergency.emergency_reason if emergency else None
        ),
        "urgency_level": (
            emergency.urgency_level if emergency else None
        ),
        "treatments": sorted(
            record.treatments,
            key=lambda item: item.treatment_id,
        ),
        "prescriptions": sorted(
            record.prescriptions,
            key=lambda item: item.prescription_id,
        ),
    }


def get_consultation(
    db: Session,
    current_user: User,
    consultation_id: int,
):
    veterinarian = get_profile(db, current_user)

    record = db.scalar(
        _details_statement(veterinarian).where(
            Consultation.consultation_id == consultation_id
        )
    )

    if record is None:
        raise HTTPException(
            404, "Consultation not found in your assigned records."
        )

    return _serialize(record)


def _lock_visit(
    db: Session,
    current_user: User,
    appointment_id: int,
):
    veterinarian = get_profile(db, current_user)

    clinic = db.scalar(
        select(Clinic)
        .where(
            Clinic.clinic_id == veterinarian.clinic_id,
            Clinic.status == "active",
        )
        .with_for_update()
    )

    if clinic is None:
        raise HTTPException(403, "Your clinic is not active.")

    location = db.execute(
        select(
            Appointment.pet_id,
            Appointment.time_slot_id,
            TimeSlot.schedule_id,
        )
        .join(
            TimeSlot,
            TimeSlot.time_slot_id == Appointment.time_slot_id,
        )
        .join(
            Schedule,
            Schedule.schedule_id == TimeSlot.schedule_id,
        )
        .where(
            Appointment.appointment_id == appointment_id,
            Appointment.veterinarian_id
            == veterinarian.veterinarian_id,
            Schedule.veterinarian_id
            == veterinarian.veterinarian_id,
        )
    ).first()

    if location is None:
        raise HTTPException(
            404, "Appointment not assigned to you."
        )

    schedule = lock_schedule(
        db, location.schedule_id, current_user
    )

    slot = db.scalar(
        select(TimeSlot)
        .where(
            TimeSlot.time_slot_id == location.time_slot_id,
            TimeSlot.schedule_id == schedule.schedule_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    pet = db.scalar(
        select(Pet)
        .where(Pet.pet_id == location.pet_id)
        .with_for_update()
    )

    appointment = db.scalar(
        select(Appointment)
        .where(
            Appointment.appointment_id == appointment_id,
            Appointment.veterinarian_id
            == veterinarian.veterinarian_id,
            Appointment.time_slot_id == location.time_slot_id,
            Appointment.pet_id == location.pet_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if slot is None or pet is None or appointment is None:
        raise HTTPException(
            409, "Appointment changed. Refresh and try again."
        )

    return veterinarian, appointment, schedule, slot


def start_consultation(
    db: Session,
    current_user: User,
    appointment_id: int,
):
    try:
        veterinarian, appointment, schedule, slot = _lock_visit(
            db, current_user, appointment_id
        )

        existing = db.scalar(
            select(Consultation)
            .where(Consultation.appointment_id == appointment_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        # Reopening a consultation never creates another record.
        if existing is not None:
            if (
                existing.veterinarian_id
                != veterinarian.veterinarian_id
                or existing.clinic_id != veterinarian.clinic_id
            ):
                raise HTTPException(
                    409, "This appointment has another consultation record."
                )

            consultation_id = existing.consultation_id
            db.commit()
            return get_consultation(
                db, current_user, consultation_id
            )

        if appointment.status != "confirmed":
            raise HTTPException(
                409, "Only confirmed appointments can start a consultation."
            )

        today = datetime.now(CLINIC_TIMEZONE).date()

        if schedule.schedule_date != today:
            raise HTTPException(
                409, "A new consultation must be started on the appointment date."
            )

        if schedule.status != "active" or slot.status != "booked":
            raise HTTPException(
                409, "This appointment does not have an active booked slot."
            )

        now = utc_now()

        record = Consultation(
            appointment_id=appointment.appointment_id,
            clinic_id=veterinarian.clinic_id,
            pet_id=appointment.pet_id,
            veterinarian_id=veterinarian.veterinarian_id,
            consultation_date=now,
            updated_at=now,
            status="draft",
            version=1,
        )

        appointment.status = "in_progress"

        db.add(record)
        db.flush()
        consultation_id = record.consultation_id
        db.commit()

        return get_consultation(
            db, current_user, consultation_id
        )

    except Exception:
        db.rollback()
        raise


def _sync_rows(
    db: Session,
    model,
    id_field: str,
    consultation_id: int,
    incoming,
    new_fields=None,
):
    existing = {
        getattr(row, id_field): row
        for row in db.scalars(
            select(model)
            .where(model.consultation_id == consultation_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        ).all()
    }

    retained = set()

    for item in incoming:
        row_id = getattr(item, id_field)

        if row_id is not None:
            row = existing.get(row_id)

            if row is None:
                raise HTTPException(
                    400,
                    "A treatment or prescription does not belong "
                    "to this consultation.",
                )

            retained.add(row_id)
        else:
            row = model(
                consultation_id=consultation_id,
                **(new_fields or {}),
            )
            db.add(row)

        changes = item.model_dump(exclude={id_field})

        for name, value in changes.items():
            setattr(row, name, value)

    # These are editable draft rows, not completed records.
    for row_id, row in existing.items():
        if row_id not in retained:
            db.delete(row)


def save_consultation(
    db: Session,
    current_user: User,
    consultation_id: int,
    data: ConsultationSave,
):
    try:
        veterinarian = get_profile(db, current_user)

        appointment_id = db.scalar(
            select(Consultation.appointment_id)
            .where(
                Consultation.consultation_id == consultation_id,
                Consultation.veterinarian_id
                == veterinarian.veterinarian_id,
                Consultation.clinic_id == veterinarian.clinic_id,
            )
        )

        if appointment_id is None:
            raise HTTPException(
                404, "Consultation not found in your assigned records."
            )

        _lock_visit(db, current_user, appointment_id)

        record = db.scalar(
            select(Consultation)
            .where(
                Consultation.consultation_id == consultation_id,
                Consultation.appointment_id == appointment_id,
                Consultation.veterinarian_id
                == veterinarian.veterinarian_id,
                Consultation.clinic_id == veterinarian.clinic_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if record is None:
            raise HTTPException(404, "Consultation not found.")

        if record.status != "draft":
            raise HTTPException(
                409, "Completed consultations cannot be edited."
            )

        if record.version != data.version:
            raise HTTPException(
                409,
                "This consultation changed in another tab. "
                "Reload it before saving.",
            )

        appointment = record.appointment

        if appointment.status != "in_progress":
            raise HTTPException(
                409, "The appointment is no longer in progress."
            )

        record.consultation_information = data.consultation_information
        record.examination_findings = data.examination_findings
        record.diagnosis = data.diagnosis
        record.notes = data.notes

        _sync_rows(
            db,
            Treatment,
            "treatment_id",
            record.consultation_id,
            data.treatments,
        )

        _sync_rows(
            db,
            Prescription,
            "prescription_id",
            record.consultation_id,
            data.prescriptions,
            new_fields={
                "veterinarian_id": record.veterinarian_id,
                "prescription_date":
                    datetime.now(CLINIC_TIMEZONE).date(),
            },
        )

        now = utc_now()
        record.updated_at = now
        record.version += 1

        if data.complete:
            record.status = "completed"
            record.completed_at = now
            appointment.status = "completed"

        db.commit()

        return get_consultation(
            db, current_user, consultation_id
        )

    except Exception:
        db.rollback()
        raise