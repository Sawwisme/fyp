from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.services.owner_medical_history_service import (
    list_medical_history,
)
from app.services.pet_service import get_owner_profile, get_pet


MALAYSIA_TIME = timezone(timedelta(hours=8))


def visit_date(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.astimezone(MALAYSIA_TIME).strftime(
            "%d %b %Y, %H:%M MYT"
        )

    return str(value) if value is not None else "Not recorded"


def medical_record_reply(db, current_user, pet_id, intent):
    if current_user.role != "pet_owner":
        raise HTTPException(
            403,
            "A pet owner account is required.",
        )

    get_owner_profile(db, current_user)

    if pet_id is None:
        return (
            "Start a pet-linked chat so I can check "
            "the correct medical records."
        )

    pet = get_pet(db, current_user, pet_id)

    records = list_medical_history(
        db=db,
        current_user=current_user,
        pet_id=pet.pet_id,
        offset=0,
        limit=3,
    )

    if not records:
        return (
            f"I do not see a completed consultation record "
            f"available to you for {pet.pet_name}. "
            "AI assessments are stored separately."
        )

    if intent == "recorded_prescriptions":
        return prescription_reply(pet.pet_name, records[0])

    sections = [
        f"Up to three recent completed consultations "
        f"for {pet.pet_name}:"
    ]

    for record in records:
        section = (
            f"Consultation #{record['consultation_id']}\n"
            f"Date: {visit_date(record['consultation_date'])}\n"
            f"Clinic: {record['clinic_name']}\n"
            f"Veterinarian: {record['veterinarian_name']}\n"
            f"Recorded diagnosis: "
            f"{record.get('diagnosis') or 'Not recorded'}"
        )

        treatments = record.get("treatments", [])

        if treatments:
            section += "\nTreatments — up to three shown:"

            for treatment in treatments[:3]:
                status = (
                    treatment.get("current_status")
                    or treatment.get("recorded_status")
                    or "Not recorded"
                )

                section += (
                    f"\n• {treatment['treatment_name']} "
                    f"— {status.replace('_', ' ')}"
                )
        else:
            section += "\nNo treatments recorded in this consultation."

        section += (
            f"\nPrescriptions recorded: "
            f"{len(record.get('prescriptions', []))}"
        )

        sections.append(section)

    sections.append(
        "These are saved veterinary records, not a new diagnosis. "
        "Open Medical History for complete details."
    )

    return "\n\n".join(sections)


def prescription_reply(pet_name, record):
    prescriptions = record.get("prescriptions", [])

    heading = (
        f"{pet_name}'s latest completed consultation "
        f"#{record['consultation_id']}\n"
        f"Date: {visit_date(record['consultation_date'])}\n"
        f"Clinic: {record['clinic_name']}\n"
        f"Veterinarian: {record['veterinarian_name']}"
    )

    if not prescriptions:
        return (
            heading
            + "\n\nNo prescriptions are recorded in this consultation. "
            "Older visits may have their own prescriptions; "
            "check Medical History."
        )

    sections = [
        heading,
        "Saved prescription instructions — up to five shown. "
        "These are historical records, not confirmation that "
        "the medicines should still be taken:",
    ]

    for prescription in prescriptions[:5]:
        sections.append(
            f"Prescription #{prescription.prescription_id}\n"
            f"Medicine: {prescription.medication_name}\n"
            f"Prescription date: {prescription.prescription_date}\n"
            f"Recorded dosage: {prescription.dosage}\n"
            f"Route: "
            f"{prescription.administration_route or 'Not recorded'}\n"
            f"Frequency: {prescription.frequency or 'Not recorded'}\n"
            f"Duration: {prescription.duration or 'Not recorded'}\n"
            f"Instructions: {prescription.instructions or 'Not recorded'}"
        )

    sections.append(
        "The chatbot has copied these fields without calculating "
        "or changing them. Do not restart or change medication "
        "based on an old record. Contact the prescribing clinic "
        "if any instructions are unclear."
    )

    return "\n\n".join(sections)