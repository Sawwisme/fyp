from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Appointment,
    Consultation,
    FollowupCare,
    PetOwner,
    Treatment,
    TreatmentProgress,
    TimeSlot,
    Veterinarian,
)
from app.services.vet_profile_service import get_profile


def get_booking_context(
    db: Session,
    current_user,
    source_type: str,
    source_id: int,
):
    veterinarian = get_profile(db, current_user)

    if source_type == "treatment":
        source = db.execute(
            select(TreatmentProgress, Consultation)
            .join(
                Treatment,
                Treatment.treatment_id
                == TreatmentProgress.treatment_id,
            )
            .join(
                Consultation,
                Consultation.consultation_id
                == Treatment.consultation_id,
            )
            .where(
                TreatmentProgress.treatment_id == source_id,
                Treatment.status == "planned",
                TreatmentProgress.status.in_(
                    ["planned", "in_progress"]
                ),
                Consultation.veterinarian_id
                == veterinarian.veterinarian_id,
                Consultation.clinic_id == veterinarian.clinic_id,
                Consultation.status == "completed",
            )
        ).first()

        link_column = Appointment.planned_treatment_id

    else:
        source = db.execute(
            select(FollowupCare, Consultation)
            .join(
                Consultation,
                Consultation.consultation_id
                == FollowupCare.consultation_id,
            )
            .where(
                FollowupCare.followup_care_id == source_id,
                FollowupCare.veterinarian_id
                == veterinarian.veterinarian_id,
                FollowupCare.status == "pending",
                Consultation.clinic_id == veterinarian.clinic_id,
                Consultation.status == "completed",
            )
        ).first()

        link_column = Appointment.followup_care_id

    if source is None:
        raise HTTPException(
            404,
            "An open plan or follow-up was not found "
            "in your assigned records.",
        )

    task, consultation = source

    original = db.scalar(
        select(Appointment)
        .where(
            Appointment.appointment_id
            == consultation.appointment_id,
        )
        .options(
            selectinload(Appointment.pet),
            selectinload(Appointment.owner)
            .selectinload(PetOwner.user),
        )
    )

    existing_id = db.scalar(
        select(Appointment.appointment_id)
        .where(
            link_column == source_id,
            Appointment.status.notin_(["cancelled", "rejected"]),
        )
        .order_by(Appointment.appointment_id.desc())
        .limit(1)
    )

    owner = original.owner

    return {
        "pet_owner_id": original.pet_owner_id,
        "pet_id": original.pet_id,
        "pet_name": original.pet.pet_name,
        "owner_name": (
            owner.user.full_name
            if owner.user is not None
            else owner.contact_name or "Not recorded"
        ),
        "veterinarian_id": veterinarian.veterinarian_id,
        "veterinarian_name": veterinarian.user.full_name,
        "recommended_date": (
            task.recommended_date
            if source_type == "followup"
            else None
        ),
        "existing_appointment_id": existing_id,
    }

def get_linked_visits(
    db: Session,
    source_type: str,
    source_ids: list[int],
    veterinarian,
):
    if not source_ids:
        return {}

    link_column = {
        "treatment": Appointment.planned_treatment_id,
        "followup": Appointment.followup_care_id,
    }[source_type]

    records = db.execute(
        select(
            link_column.label("source_id"),
            Appointment.appointment_id,
            Appointment.appointment_date,
            TimeSlot.start_time,
            TimeSlot.end_time,
            Appointment.status,
            Consultation.consultation_id,
            Consultation.status.label("consultation_status"),
        )
        .join(
            TimeSlot,
            TimeSlot.time_slot_id == Appointment.time_slot_id,
        )
        .join(
            Veterinarian,
            Veterinarian.veterinarian_id
            == Appointment.veterinarian_id,
        )
        .outerjoin(
            Consultation,
            Consultation.appointment_id
            == Appointment.appointment_id,
        )
        .where(
            link_column.in_(source_ids),
            Appointment.veterinarian_id
            == veterinarian.veterinarian_id,
            Veterinarian.clinic_id == veterinarian.clinic_id,
        )
        .order_by(
            Appointment.status.in_(["cancelled", "rejected"]).asc(),
            Appointment.appointment_id.desc(),
        )
    ).mappings().all()

    result = {}

    for row in records:
        # Prefer an existing non-cancelled visit.
        # Otherwise show the latest cancelled/rejected booking.
        if row["source_id"] not in result:
            item = dict(row)
            source_id = item.pop("source_id")
            result[source_id] = item

    return result