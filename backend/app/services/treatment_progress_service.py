from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Consultation,
    Treatment,
    TreatmentProgress,
    User,
)
from app.schemas.treatment_progress import (
    TreatmentProgressResponse,
    TreatmentProgressUpdate,
)
from app.services.vet_profile_service import get_profile


def update_progress(
    db: Session,
    current_user: User,
    treatment_id: int,
    data: TreatmentProgressUpdate,
):
    try:
        veterinarian = get_profile(db, current_user)

        source = db.execute(
            select(Treatment, Consultation)
            .join(
                Consultation,
                Consultation.consultation_id
                == Treatment.consultation_id,
            )
            .where(
                Treatment.treatment_id == treatment_id,
                Consultation.clinic_id == veterinarian.clinic_id,
                Consultation.veterinarian_id
                == veterinarian.veterinarian_id,
                Consultation.status == "completed",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        ).first()

        if source is None:
            raise HTTPException(
                404,
                "Treatment plan not found in your assigned records.",
            )

        treatment, original = source

        if treatment.status != "planned":
            raise HTTPException(
                409,
                "Only finalized planned treatments "
                "use this progress workflow.",
            )

        progress = db.scalar(
            select(TreatmentProgress)
            .where(
                TreatmentProgress.treatment_id == treatment_id
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if progress is None:
            raise HTTPException(
                409,
                "Treatment tracking has not been initialized.",
            )

        if progress.version != data.version:
            raise HTTPException(
                409,
                "This treatment changed. Refresh before trying again.",
            )

        allowed = {
            "planned": {"in_progress", "completed", "cancelled"},
            "in_progress": {"completed", "cancelled"},
        }

        if data.status not in allowed.get(progress.status, set()):
            raise HTTPException(
                409,
                "This treatment status change is not allowed.",
            )

        if data.status == "completed":
            completion = db.scalar(
                select(Consultation)
                .where(
                    Consultation.consultation_id
                    == data.completion_consultation_id,
                    Consultation.consultation_id
                    != original.consultation_id,
                    Consultation.pet_id == original.pet_id,
                    Consultation.clinic_id == original.clinic_id,
                    Consultation.veterinarian_id
                    == veterinarian.veterinarian_id,
                    Consultation.status == "completed",
                    Consultation.consultation_date
                    >= original.consultation_date,
                )
                .with_for_update()
            )

            if completion is None:
                raise HTTPException(
                    400,
                    "Choose a later completed consultation "
                    "for this patient in your assigned records.",
                )

            progress.completion_consultation_id = (
                completion.consultation_id
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if data.status == "in_progress":
            progress.started_at = now
        elif data.status == "completed":
            progress.completed_at = now
        else:
            progress.cancelled_at = now
            progress.cancellation_reason = data.cancellation_reason

        progress.status = data.status
        progress.updated_by_user_id = current_user.user_id
        progress.updated_at = now
        progress.version += 1

        result = TreatmentProgressResponse.model_validate(progress)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise

def list_completion_consultations(
    db: Session,
    current_user: User,
    treatment_id: int,
    offset: int,
    limit: int,
):
    veterinarian = get_profile(db, current_user)

    original = db.scalar(
        select(Consultation)
        .join(
            Treatment,
            Treatment.consultation_id
            == Consultation.consultation_id,
        )
        .where(
            Treatment.treatment_id == treatment_id,
            Treatment.status == "planned",
            Consultation.status == "completed",
            Consultation.clinic_id == veterinarian.clinic_id,
            Consultation.veterinarian_id
            == veterinarian.veterinarian_id,
        )
    )

    if original is None:
        raise HTTPException(
            404,
            "Treatment plan not found in your assigned records.",
        )

    return db.execute(
        select(
            Consultation.consultation_id,
            Consultation.consultation_date,
            Consultation.diagnosis,
        )
        .where(
            Consultation.consultation_id
            != original.consultation_id,
            Consultation.pet_id == original.pet_id,
            Consultation.clinic_id == original.clinic_id,
            Consultation.veterinarian_id
            == veterinarian.veterinarian_id,
            Consultation.status == "completed",
            Consultation.consultation_date
            >= original.consultation_date,
        )
        .order_by(
            Consultation.consultation_date.desc(),
            Consultation.consultation_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).mappings().all()