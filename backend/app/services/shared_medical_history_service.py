from datetime import timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import (
    Appointment,
    Consultation,
    Pet,
    Schedule,
    TimeSlot,
    Veterinarian,
)
from app.services.vet_profile_service import get_profile


def list_shared_history(
    db, current_user, appointment_id, offset=0, limit=20
):
    vet = get_profile(db, current_user)

    appointment = db.scalar(
        select(Appointment)
        .join(TimeSlot, TimeSlot.time_slot_id == Appointment.time_slot_id)
        .join(Schedule, Schedule.schedule_id == TimeSlot.schedule_id)
        .join(Pet, Pet.pet_id == Appointment.pet_id)
        .where(
            Appointment.appointment_id == appointment_id,
            Appointment.veterinarian_id == vet.veterinarian_id,
            Schedule.veterinarian_id == vet.veterinarian_id,
            Appointment.status.in_([
                "confirmed", "in_progress", "completed",
            ]),
            Appointment.medical_history_shared_at.is_not(None),
            Pet.pet_owner_id == Appointment.pet_owner_id,
        )
    )

    if appointment is None:
        raise HTTPException(
            404,
            "Shared medical history is not available "
            "for this appointment.",
        )

    shared_at = appointment.medical_history_shared_at

    records = db.scalars(
        select(Consultation)
        .join(
            Appointment,
            Appointment.appointment_id == Consultation.appointment_id,
        )
        .where(
            Consultation.pet_id == appointment.pet_id,
            Appointment.pet_id == appointment.pet_id,
            Appointment.pet_owner_id == appointment.pet_owner_id,
            Consultation.status == "completed",
            Consultation.completed_at.is_not(None),
            Consultation.completed_at <= shared_at,
            Consultation.appointment_id != appointment.appointment_id,
        )
        .options(
            selectinload(Consultation.clinic),
            selectinload(Consultation.veterinarian)
            .selectinload(Veterinarian.user),
            selectinload(Consultation.treatments),
            selectinload(Consultation.prescriptions),
        )
        .order_by(
            Consultation.consultation_date.desc(),
            Consultation.consultation_id.desc(),
        )
        .offset(offset)
        .limit(limit + 1)
    ).all()

    items = []

    for record in records[:limit]:
        vet_user = (
            record.veterinarian.user
            if record.veterinarian is not None
            else None
        )

        items.append({
            "consultation_id": record.consultation_id,
            "consultation_date": record.consultation_date,
            "clinic_name": (
                record.clinic.clinic_name
                if record.clinic is not None
                else "Not recorded"
            ),
            "veterinarian_name": (
                vet_user.full_name if vet_user else "Not recorded"
            ),
            "diagnosis": record.diagnosis,
            "examination_findings": record.examination_findings,
            "followup_instructions": record.followup_instructions,
            "treatments": [
                {
                    "treatment_name": treatment.treatment_name,
                    "description": treatment.description,
                    "treatment_date": treatment.treatment_date,
                    "status": treatment.status,
                }
                for treatment in sorted(
                    record.treatments,
                    key=lambda item: item.treatment_id,
                )
            ],
            "prescriptions": [
                {
                    "medication_name": prescription.medication_name,
                    "dosage": prescription.dosage,
                    "administration_route":
                        prescription.administration_route,
                    "frequency": prescription.frequency,
                    "duration": prescription.duration,
                    "instructions": prescription.instructions,
                    "prescription_date": prescription.prescription_date,
                }
                for prescription in sorted(
                    record.prescriptions,
                    key=lambda item: item.prescription_id,
                )
            ],
        })

    if shared_at.tzinfo is None:
        shared_at = shared_at.replace(tzinfo=timezone.utc)

    return {
        "appointment_id": appointment.appointment_id,
        "pet_id": appointment.pet_id,
        "shared_at": shared_at,
        "items": items,
        "has_more": len(records) > limit,
    }