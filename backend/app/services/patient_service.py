"""Read-only patient directory, scoped to the signed-in vet and clinic."""
from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from app.models import (Pet, PetOwner, User, Appointment, Schedule, TimeSlot,
                        Consultation, Treatment, Prescription, FollowupCare, Veterinarian)
from app.services.vet_profile_service import get_profile


def appointments(vet):
    return (select(Appointment).join(TimeSlot).join(Schedule).join(Veterinarian, Schedule.veterinarian_id == Veterinarian.veterinarian_id).where(
        Appointment.veterinarian_id == vet.veterinarian_id,
        Schedule.veterinarian_id == vet.veterinarian_id,
        Veterinarian.clinic_id == vet.clinic_id,
    ))


def consultations(vet):
    return select(Consultation).where(
        Consultation.veterinarian_id == vet.veterinarian_id,
        Consultation.clinic_id == vet.clinic_id,
    )


def patient_scope(vet):
    appointment_ids = appointments(vet).with_only_columns(Appointment.pet_id)
    consultation_ids = consultations(vet).with_only_columns(Consultation.pet_id)
    return select(Pet).where(or_(Pet.pet_id.in_(appointment_ids),
                                        Pet.pet_id.in_(consultation_ids)))


def serialize_pet(pet):
    owner = pet.owner
    user = owner.user
    return dict(pet_id=pet.pet_id, pet_name=pet.pet_name,
                species=pet.species, breed=pet.breed, gender=pet.gender,
                date_of_birth=pet.date_of_birth, weight=pet.weight,
                owner_name=user.full_name if user else owner.contact_name,
                owner_phone=user.phone_number if user else owner.contact_phone,
                owner_email=user.email if user else owner.contact_email)


def list_patients(db, user, search, offset, limit):
    vet = get_profile(db, user)
    statement = patient_scope(vet).join(PetOwner).outerjoin(User)
    if search and search.strip():
        pattern = '%' + search.strip().replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
        statement = statement.where(or_(
            Pet.pet_name.ilike(pattern, escape='!'),
            User.full_name.ilike(pattern, escape='!'),
            PetOwner.contact_name.ilike(pattern, escape='!'),
        ))
    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    pets = db.scalars(statement.options(selectinload(Pet.owner).selectinload(PetOwner.user))
                      .order_by(Pet.pet_name, Pet.pet_id).offset(offset).limit(limit)).all()
    return dict(total=total, items=[serialize_pet(pet) for pet in pets])


def patient_records(db, user, pet_id, kind, offset, limit):
    vet = get_profile(db, user)
    pet = db.scalar(patient_scope(vet).where(Pet.pet_id == pet_id).options(
        selectinload(Pet.owner).selectinload(PetOwner.user)))
    if pet is None:
        raise HTTPException(404, 'Patient not found.')
    consult = consultations(vet).where(Consultation.pet_id == pet_id)
    consult_ids = consult.with_only_columns(Consultation.consultation_id)
    if kind == 'appointments':
        statement = appointments(vet).where(Appointment.pet_id == pet_id)
        statement = statement.order_by(Appointment.appointment_date.desc(), Appointment.appointment_id.desc())
    elif kind == 'consultations':
        statement = consult.order_by(Consultation.consultation_date.desc(), Consultation.consultation_id.desc())
    elif kind == 'treatments':
        statement = select(Treatment).where(Treatment.consultation_id.in_(consult_ids)).order_by(Treatment.treatment_date.desc(), Treatment.treatment_id.desc())
    elif kind == 'prescriptions':
        statement = select(Prescription).where(Prescription.consultation_id.in_(consult_ids)).order_by(Prescription.prescription_date.desc(), Prescription.prescription_id.desc())
    else:
        statement = select(FollowupCare).where(FollowupCare.consultation_id.in_(consult_ids), FollowupCare.veterinarian_id == vet.veterinarian_id).order_by(FollowupCare.followup_care_id.desc())
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    records = db.scalars(statement.offset(offset).limit(limit)).all()
    items = []
    for record in records:
        if kind == 'appointments':
            item = dict(id=record.appointment_id, date=record.appointment_date,
                        title=record.appointment_type, status=record.status)
        elif kind == 'consultations':
            item = dict(id=record.consultation_id, consultation_id=record.consultation_id,
                        date=record.consultation_date, title=record.diagnosis or 'Diagnosis not recorded', status=record.status)
        elif kind == 'treatments':
            item = dict(id=record.treatment_id, consultation_id=record.consultation_id,
                        date=record.treatment_date, title=record.treatment_name, status=record.status,
                        details=record.description)
        elif kind == 'prescriptions':
            item = dict(id=record.prescription_id, consultation_id=record.consultation_id,
                        date=record.prescription_date, title=record.medication_name,
                        details=' · '.join(filter(None, [record.dosage, record.administration_route,
                            record.frequency, record.duration, record.instructions])))
        else:
            item = dict(id=record.followup_care_id, consultation_id=record.consultation_id,
                        date=record.recommended_date, title=record.reason or 'Follow-up review',
                        status=record.status, details=record.care_instructions)
        items.append(item)
    return dict(patient=serialize_pet(pet), total=total, items=items)
