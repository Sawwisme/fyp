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
from app.services.chatbot_language_service import (
    render_followup_care,
)

STATE_LABELS = {
    "action_needed": "An owner update can be submitted",
    "awaiting_review": "Your submitted update is awaiting vet review",
    "update_requested": "The vet requested another update",
    "visit_required": "An in-clinic review is required",
    "reviewed": "The submitted update has been reviewed",
    "completed": "Completed",
    "cancelled": "Cancelled",
}


def followup_care_reply(
    db,
    current_user,
    pet_id,
    language="en",
):
    if current_user.role != "pet_owner":
        raise HTTPException(
            403,
            "A pet owner account is required.",
        )

    owner = get_owner_profile(db, current_user)

    if pet_id is None:
        return render_followup_care(
            None, [], language=language
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



    tasks = []

    for followup, clinic_name in records:
        state = get_owner_submission_state(
            db,
            current_user,
            followup.followup_care_id,
        )

        tasks.append({
            "followup_id": followup.followup_care_id,
            "clinic_name": clinic_name,
            "state": state["submission_state"],
            "can_submit": state["can_submit"],
            "date": (
                followup.recommended_date.strftime("%d %b %Y")
                if followup.recommended_date is not None
                else None
            ),
            "reason": followup.reason,
            "care_instructions": followup.care_instructions,
            "photos_required": followup.photos_required,
            "photo_instructions": followup.photo_instructions,
            "visit_required": followup.visit_required,
        })

    return render_followup_care(
        pet.pet_name,
        tasks,
        language=language,
    )