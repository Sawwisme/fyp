from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    Appointment,
    Clinic,
    Consultation,
    FollowupCare,
    Pet,
)
from app.services.followup_submission_service import (
    get_owner_submission_state,
)
from app.services.pet_service import get_owner_profile, get_pet


STATE_LABELS = {
    "action_needed": "An owner update can be submitted",
    "awaiting_review": "Your submitted update is awaiting vet review",
    "update_requested": "The vet requested another update",
    "visit_required": "An in-clinic review is required",
    "reviewed": "The submitted update has been reviewed",
    "completed": "Completed",
    "cancelled": "Cancelled",
}


def followup_care_reply(db, current_user, pet_id):
    if current_user.role != "pet_owner":
        raise HTTPException(
            403,
            "A pet owner account is required.",
        )

    owner = get_owner_profile(db, current_user)

    if pet_id is None:
        return (
            "Start a chat linked to your pet so I can "
            "check its follow-up instructions."
        )

    pet = get_pet(db, current_user, pet_id)

    records = db.execute(
        select(
            FollowupCare,
            Clinic.clinic_name,
        )
        .join(
            Consultation,
            Consultation.consultation_id
            == FollowupCare.consultation_id,
        )
        .join(
            Appointment,
            Appointment.appointment_id
            == Consultation.appointment_id,
        )
        .join(
            Pet,
            Pet.pet_id == FollowupCare.pet_id,
        )
        .join(
            Clinic,
            Clinic.clinic_id == Consultation.clinic_id,
        )
        .where(
            FollowupCare.pet_id == pet.pet_id,
            Consultation.pet_id == pet.pet_id,
            Appointment.pet_id == pet.pet_id,
            Pet.pet_owner_id == owner.pet_owner_id,
            Appointment.pet_owner_id == owner.pet_owner_id,
            Consultation.status == "completed",
            FollowupCare.status == "pending",
        )
        .order_by(
            Consultation.consultation_date.desc(),
            FollowupCare.followup_care_id.desc(),
        )
        .limit(3)
    ).all()

    if not records:
        return (
            f"I do not see an open follow-up task for {pet.pet_name}. "
            "Open Follow-up Care in Booking to check completed "
            "or cancelled tasks."
        )

    sections = [
        f"Recent open follow-up tasks for {pet.pet_name}:"
    ]

    for followup, clinic_name in records:
        state = get_owner_submission_state(
            db,
            current_user,
            followup.followup_care_id,
        )

        progress = STATE_LABELS.get(
            state["submission_state"],
            "Check the task details",
        )

        date = (
            followup.recommended_date.strftime("%d %b %Y")
            if followup.recommended_date is not None
            else "Not recorded"
        )

        section = (
            f"Follow-up #{followup.followup_care_id}\n"
            f"Clinic: {clinic_name}\n"
            f"Status: {progress}\n"
            f"Recommended review date: {date}\n"
            f"Reason: {followup.reason or 'Not recorded'}\n"
            f"Vet's home-care instructions: "
            f"{followup.care_instructions or 'Not recorded'}"
        )

        if followup.photos_required:
            section += (
                "\nPhotos requested: Yes\n"
                "Photo instructions: "
                f"{followup.photo_instructions or 'Check with the clinic'}"
            )

        if state["can_submit"]:
            section += (
                "\nYou can submit an update through this task "
                "in Follow-up Care."
            )
        else:
            section += (
                "\nAnother submission is not currently allowed. "
                "Check the task for feedback or further instructions."
            )

        if followup.visit_required:
            section += (
                "\nAn in-clinic review is required. "
                "Check the linked appointment in the task, "
                "or choose a time if none is booked."
            )

        sections.append(section)

    sections.append(
        "A recommended review date is not a booked appointment. "
        "This chat has not submitted photos, booked a visit "
        "or completed a follow-up."
    )

    return "\n\n".join(sections)