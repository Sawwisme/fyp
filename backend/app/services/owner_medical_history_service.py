from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Appointment,
    Consultation,
    Pet,
    Treatment,
    User,
    Veterinarian,
)
from app.services.pet_service import get_owner_profile


def list_medical_history(
    db: Session,
    current_user: User,
    pet_id: int,
    offset: int,
    limit: int,
):
    owner = get_owner_profile(db, current_user)

    pet = db.scalar(
        select(Pet).where(
            Pet.pet_id == pet_id,
            Pet.pet_owner_id == owner.pet_owner_id,
        )
    )

    if pet is None:
        raise HTTPException(404, "Pet not found.")

    records = db.scalars(
        select(Consultation)
        .join(
            Appointment,
            Appointment.appointment_id
            == Consultation.appointment_id,
        )
        .join(Pet, Pet.pet_id == Consultation.pet_id)
        .where(
            Consultation.pet_id == pet_id,
            Consultation.status == "completed",
            Pet.pet_owner_id == owner.pet_owner_id,
            Appointment.pet_owner_id == owner.pet_owner_id,
        )
        .options(
            selectinload(Consultation.clinic),
            selectinload(Consultation.veterinarian)
            .selectinload(Veterinarian.user),
            selectinload(Consultation.treatments)
            .selectinload(Treatment.progress_record),
            selectinload(Consultation.prescriptions),
            selectinload(Consultation.followups),
        )
        .order_by(
            Consultation.consultation_date.desc(),
            Consultation.consultation_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    result = []

    for record in records:
        treatments = []

        for treatment in sorted(
            record.treatments,
            key=lambda item: item.treatment_id,
        ):
            progress = treatment.progress_record

            treatments.append({
                "treatment_id": treatment.treatment_id,
                "treatment_name": treatment.treatment_name,
                "description": treatment.description,
                "treatment_date": treatment.treatment_date,
                "recorded_status": treatment.status,
                "current_status": (
                    progress.status
                    if progress is not None
                    else treatment.status
                ),
            })

        result.append({
            "consultation_id": record.consultation_id,
            "appointment_id": record.appointment_id,
            "pet_id": record.pet_id,
            "pet_name": pet.pet_name,
            "consultation_date": record.consultation_date,
            "clinic_name": record.clinic.clinic_name,
            "veterinarian_name": (
                record.veterinarian.user.full_name
            ),
            "diagnosis": record.diagnosis,
            "treatments": treatments,
            "prescriptions": sorted(
                record.prescriptions,
                key=lambda item: item.prescription_id,
            ),
            "followups": sorted(
                record.followups,
                key=lambda item: item.followup_care_id,
            ),
        })

    return result