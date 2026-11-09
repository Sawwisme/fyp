from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.services.vet_absence_service import reject_absent_slots
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
    AIAnalysisResult,
    DentalImage,
    Veterinarian,
    FollowupCare,
    TreatmentProgress,
    AIAssessmentReview,
)
from app.schemas.consultations import ConsultationSave
from app.services.schedule_service import lock_schedule
from app.services.vet_profile_service import get_profile
from app.services.return_visit_service import get_linked_visits


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
            selectinload(Consultation.treatments)
            .selectinload(Treatment.progress_record),
            selectinload(Consultation.prescriptions),
            selectinload(Consultation.ai_analysis)
            .selectinload(AIAnalysisResult.predictions),
            selectinload(Consultation.appointment)
            .selectinload(Appointment.time_slot),
            selectinload(Consultation.veterinarian)
            .selectinload(Veterinarian.user),
            selectinload(Consultation.appointment)
            .selectinload(Appointment.treatment_plan)
            .selectinload(TreatmentProgress.treatment),
            selectinload(Consultation.appointment)
            .selectinload(Appointment.followup_task),
            selectinload(Consultation.clinic),
        )
        .execution_options(populate_existing=True)
    )


def _serialize(record):
    owner = record.appointment.owner
    emergency = record.appointment.emergency_request

    appointment = record.appointment
    slot = appointment.time_slot

    return_visit = None

    if appointment.treatment_plan is not None:
        treatment = appointment.treatment_plan.treatment

        return_visit = {
            "source_type": "treatment",
            "source_id": treatment.treatment_id,
            "original_consultation_id": treatment.consultation_id,
            "title": treatment.treatment_name,
            "reason": treatment.description,
            "care_instructions": None,
        }

    elif appointment.followup_task is not None:
        followup = appointment.followup_task

        return_visit = {
            "source_type": "followup",
            "source_id": followup.followup_care_id,
            "original_consultation_id": followup.consultation_id,
            "title": "Follow-up review",
            "reason": followup.reason,
            "care_instructions": followup.care_instructions,
        }

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
        "patient": record.pet,
        "ai_analysis_id": record.ai_analysis_id,
        "ai_assessment": record.ai_analysis,

        "appointment": {
            "appointment_id": appointment.appointment_id,
            "appointment_date": appointment.appointment_date,
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "appointment_type": appointment.appointment_type,
            "appointment_source": appointment.appointment_source,
            "status": appointment.status,
            "veterinarian_name": (
                record.veterinarian.user.full_name
            ),
        },

        "followup_required": record.followup_required,
        "followup_recommended_date": (
            record.followup_recommended_date
        ),
        "followup_reason": record.followup_reason,
        "followup_instructions": record.followup_instructions,
        "return_visit": return_visit,
        "prescription_header": {
            "clinic_name": record.clinic.clinic_name,
            "clinic_address": record.clinic.address,
            "clinic_phone": record.clinic.phone_number,
            "clinic_email": record.clinic.email,
            "veterinarian_name": (
                record.veterinarian.user.full_name
            ),
            "registration_number": (
                record.veterinarian.registration_number
            ),
        },
        "followup_photos_required": record.followup_photos_required,
        "followup_photo_instructions": (
            record.followup_photo_instructions
        ),
        "followup_visit_required": record.followup_visit_required,
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
        reject_absent_slots(db, [slot.time_slot_id])

        linked_analysis_id = None

        if appointment.ai_assessment_review_id is not None:
            review = db.scalar(
                select(AIAssessmentReview)
                .join(
                    AIAnalysisResult,
                    AIAnalysisResult.analysis_id
                    == AIAssessmentReview.analysis_id,
                )
                .join(
                    DentalImage,
                    DentalImage.dental_image_id
                    == AIAnalysisResult.dental_image_id,
                )
                .where(
                    AIAssessmentReview.review_id
                    == appointment.ai_assessment_review_id,
                    AIAssessmentReview.clinic_id
                    == veterinarian.clinic_id,
                    AIAssessmentReview.status == "reviewed",
                    DentalImage.pet_id == appointment.pet_id,
                )
            )

            if review is None:
                raise HTTPException(
                    409,
                    "The linked assessment review does not match "
                    "this appointment's pet and clinic.",
                )

            linked_analysis_id = review.analysis_id

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
            ai_analysis_id=linked_analysis_id,
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

def _initialize_treatment_progress(
    db: Session,
    record: Consultation,
    current_user: User,
    now: datetime,
):
    # Assign IDs to newly added treatments before querying them.
    db.flush()

    planned_treatments = db.scalars(
        select(Treatment)
        .where(
            Treatment.consultation_id == record.consultation_id,
            Treatment.status == "planned",
        )
        .with_for_update()
    ).all()

    for treatment in planned_treatments:
        existing = db.get(
            TreatmentProgress,
            treatment.treatment_id,
        )

        if existing is None:
            db.add(
                TreatmentProgress(
                    treatment_id=treatment.treatment_id,
                    status="planned",
                    updated_by_user_id=current_user.user_id,
                    updated_at=now,
                    version=1,
                )
            )

def _complete_return_followup(
    db: Session,
    record: Consultation,
    now: datetime,
):
    followup_id = record.appointment.followup_care_id

    if followup_id is None:
        return

    followup = db.scalar(
        select(FollowupCare)
        .where(
            FollowupCare.followup_care_id == followup_id,
            FollowupCare.pet_id == record.pet_id,
            FollowupCare.veterinarian_id == record.veterinarian_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if followup is None:
        raise HTTPException(
            409,
            "The linked follow-up does not match this visit.",
        )

    if followup.status != "pending":
        raise HTTPException(
            409,
            "The linked follow-up is no longer pending. "
            "Check its status before completing this consultation.",
        )

    followup.assessment_information = (
        f"Examination findings:\n{record.examination_findings}\n\n"
        f"Diagnosis:\n{record.diagnosis}"
    )
    followup.notes = record.notes
    followup.followup_date = now
    followup.status = "completed"

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

        if "ai_analysis_id" in data.model_fields_set:
            if data.ai_analysis_id is not None:
                assessment = db.scalar(
                    select(AIAnalysisResult)
                    .join(
                        DentalImage,
                        DentalImage.dental_image_id
                        == AIAnalysisResult.dental_image_id,
                    )
                    .where(
                        AIAnalysisResult.analysis_id
                        == data.ai_analysis_id,
                        DentalImage.pet_id == record.pet_id,
                    )
                    .with_for_update()
                )

                if assessment is None:
                    raise HTTPException(
                        400,
                        "The selected AI assessment does not "
                        "belong to this patient.",
                    )

            record.ai_analysis_id = data.ai_analysis_id

        followup_fields = (
            "followup_required",
            "followup_recommended_date",
            "followup_reason",
            "followup_instructions",
            "followup_photos_required",
            "followup_photo_instructions",
            "followup_visit_required",
        )

        # Preserve existing values if an older client omits them.
        for field in followup_fields:
            if field in data.model_fields_set:
                setattr(record, field, getattr(data, field))

        if not record.followup_required:
            record.followup_recommended_date = None
            record.followup_reason = None
            record.followup_instructions = None
            record.followup_photos_required = False
            record.followup_photo_instructions = None
            record.followup_visit_required = False

        if not record.followup_photos_required:
            record.followup_photo_instructions = None

        if (
            data.complete
            and record.followup_required
            and record.followup_photos_required
            and not (
                record.followup_photo_instructions
                and record.followup_photo_instructions.strip()
            )
        ):
            raise HTTPException(
                422,
                "Describe the photos the owner needs to submit.",
            )

        if data.complete and record.followup_required:
            today = datetime.now(CLINIC_TIMEZONE).date()

            if record.followup_recommended_date is None:
                raise HTTPException(
                    422,
                    "Enter the recommended follow-up date.",
                )

            if record.followup_recommended_date < today:
                raise HTTPException(
                    422,
                    "The recommended follow-up date "
                    "cannot be in the past.",
                )

            if not (
                record.followup_reason
                and record.followup_reason.strip()
            ):
                raise HTTPException(
                    422,
                    "Enter the reason for follow-up.",
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
            
            _complete_return_followup(
                db,
                record,
                now,
            )

            _initialize_treatment_progress(
                db,
                record,
                current_user,
                now,
            )

            if record.followup_required:
                db.add(
                    FollowupCare(
                        consultation_id=record.consultation_id,
                        pet_id=record.pet_id,
                        veterinarian_id=record.veterinarian_id,
                        recommended_date=(
                            record.followup_recommended_date
                        ),
                        reason=record.followup_reason,
                        care_instructions=(
                            record.followup_instructions
                        ),
                        followup_date=None,
                        assessment_information=None,
                        status="pending",
                        notes=None,
                        photos_required=(
                            record.followup_photos_required
                        ),
                        photo_instructions=(
                            record.followup_photo_instructions
                        ),
                        visit_required=(
                            record.followup_visit_required
                        ),
                    )
                )

        db.commit()

        return get_consultation(
            db, current_user, consultation_id
        )

    except Exception:
        db.rollback()
        raise

def list_my_consultations(
    db: Session,
    current_user: User,
    search: str | None,
    consultation_status: str | None,
    offset: int,
    limit: int,
    counts_only: bool = False,
):
    veterinarian = get_profile(db, current_user)

    owner_name = func.coalesce(
        User.full_name,
        PetOwner.contact_name,
        "Not recorded",
    )

    statement = (
        select(
            Consultation.consultation_id,
            Consultation.appointment_id,
            Consultation.consultation_date,
            Pet.pet_name,
            owner_name.label("owner_name"),
            Consultation.diagnosis,
            Consultation.status,
        )
        .join(Pet, Pet.pet_id == Consultation.pet_id)
        .join(
            Appointment,
            Appointment.appointment_id == Consultation.appointment_id,
        )
        .join(
            PetOwner,
            PetOwner.pet_owner_id == Appointment.pet_owner_id,
        )
        .outerjoin(User, User.user_id == PetOwner.user_id)
        .where(
            Consultation.veterinarian_id
            == veterinarian.veterinarian_id,
            Consultation.clinic_id == veterinarian.clinic_id,
        )
    )

    if consultation_status is not None:
        statement = statement.where(
            Consultation.status == consultation_status
        )

    if search and search.strip():
            term = search.strip().lower()
    
            statement = statement.where(
                or_(
                    func.lower(Pet.pet_name).contains(
                        term, autoescape=True
                    ),
                    func.lower(owner_name).contains(
                        term, autoescape=True
                    ),
                )
            )

    if counts_only:
        filtered = statement.subquery()

        return db.execute(
            select(
                func.count().label("total"),
                func.coalesce(
                    func.sum(
                        case(
                            (filtered.c.status == "draft", 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("draft"),
                func.coalesce(
                    func.sum(
                        case(
                            (filtered.c.status == "completed", 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("completed"),
            )
            .select_from(filtered)
        ).mappings().one()


    statement = (
        statement
        .order_by(
            Consultation.consultation_date.desc(),
            Consultation.consultation_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return db.execute(statement).mappings().all()

    


def list_my_clinical_history(
    db: Session,
    current_user: User,
    record_type: str,
    search: str | None,
    consultation_status: str | None,
    offset: int,
    limit: int,
    date_from: date | None = None,
    date_to: date | None = None,
    counts_only: bool = False,
    treatment_status: str | None = None,
):
    veterinarian = get_profile(db, current_user)

    models = {
        "treatments": Treatment,
        "prescriptions": Prescription,
    }
    model = models[record_type]

    if record_type == "treatments":
        name_column = Treatment.treatment_name
        date_column = Treatment.treatment_date
        id_column = Treatment.treatment_id
    else:
        name_column = Prescription.medication_name
        date_column = Prescription.prescription_date
        id_column = Prescription.prescription_id

    owner_name = func.coalesce(
        User.full_name,
        PetOwner.contact_name,
        "Not recorded",
    )

    statement = (
        select(
            model,
            Pet.pet_name,
            owner_name.label("owner_name"),
            Consultation.status.label("consultation_status"),
        )
        .select_from(model)
        .join(model.consultation)
        .join(Consultation.pet)
        .join(Consultation.appointment)
        .join(Appointment.owner)
        .outerjoin(PetOwner.user)
        .where(
            Consultation.veterinarian_id
            == veterinarian.veterinarian_id,
            Consultation.clinic_id == veterinarian.clinic_id,
        )
    )

    if record_type == "treatments":
        statement = (
            statement
            .options(selectinload(Treatment.progress_record))
            .outerjoin(
                TreatmentProgress,
                TreatmentProgress.treatment_id
                == Treatment.treatment_id,
            )
            .add_columns(
                func.coalesce(
                    TreatmentProgress.status,
                    Treatment.status,
                ).label("effective_status"),
                TreatmentProgress.version.label("progress_version"),
            )
        )

    if record_type == "prescriptions":
        statement = statement.where(
            Prescription.veterinarian_id
            == veterinarian.veterinarian_id
        )

    if treatment_status is not None:
        if record_type != "treatments":
            raise HTTPException(
                422,
                "Treatment status applies to treatments only.",
            )

        statement = statement.where(
            func.coalesce(
                TreatmentProgress.status,
                Treatment.status,
            ) == treatment_status
        )

    if consultation_status is not None:
        statement = statement.where(
            Consultation.status == consultation_status
        )

    if search and search.strip():
        term = search.strip().lower()

        statement = statement.where(
            or_(
                func.lower(Pet.pet_name).contains(
                    term, autoescape=True
                ),
                func.lower(owner_name).contains(
                    term, autoescape=True
                ),
                func.lower(name_column).contains(
                    term, autoescape=True
                ),
            )
        )

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            422,
            "Start date must be on or before end date.",
        )

    if date_from:
        statement = statement.where(date_column >= date_from)

    if date_to:
        statement = statement.where(date_column <= date_to)

    if counts_only:
        today = datetime.now(CLINIC_TIMEZONE).date()
        month_start = today.replace(day=1)

        next_month = (
            date(today.year + 1, 1, 1)
            if today.month == 12
            else date(today.year, today.month + 1, 1)
        )

        filtered = statement.subquery()
        record_date = filtered.c[date_column.key]
        consultation_status_column = (
            filtered.c.consultation_status
        )

        planned_count = (
            func.coalesce(
                func.sum(
                    case(
                        (filtered.c.effective_status == "planned", 1),
                        else_=0,
                    )
                ),
                0,
            )
            if record_type == "treatments"
            else 0
        )

        completed_count = (
            func.coalesce(
                func.sum(
                    case(
                        (filtered.c.effective_status == "completed", 1),
                        else_=0,
                    )
                ),
                0,
            )
            if record_type == "treatments"
            else 0
        )

        in_progress_count = (
            func.coalesce(
                func.sum(
                    case(
                        (
                            filtered.c.effective_status
                            == "in_progress",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            )
            if record_type == "treatments"
            else 0
        )

        return db.execute(
            select(
                func.count().label("total"),
                func.coalesce(
                    in_progress_count, 0
                ).label("in_progress"),
                func.coalesce(
                    planned_count, 0
                ).label("planned"),
                func.coalesce(
                    completed_count, 0
                ).label("completed"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                consultation_status_column == "draft",
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("draft"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                consultation_status_column
                                == "completed",
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("finalized"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (record_date >= month_start)
                                & (record_date < next_month),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("this_month"),
            ).select_from(filtered)
        ).mappings().one()

    records = db.execute(
        statement
        .order_by(date_column.desc(), id_column.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    result = []

    for row in records:
        record, pet_name, owner_name, consultation_status = row[:4]

        item = {
            column.name: getattr(record, column.name)
            for column in model.__table__.columns
        }

        item.update({
            "pet_name": pet_name,
            "owner_name": owner_name,
            "consultation_status": consultation_status,
        })

        if record_type == "treatments":
            item["recorded_status"] = record.status
            item["status"] = row[4]
            item["progress_version"] = row[5]
            item["progress_record"] = record.progress_record

        result.append(item)

    if record_type == "treatments":
        linked_visits = get_linked_visits(
            db,
            "treatment",
            [item["treatment_id"] for item in result],
            veterinarian,
        )

        for item in result:
            item["linked_visit"] = linked_visits.get(
                item["treatment_id"]
            )

    return result

def list_consultation_assessments(
    db: Session,
    current_user: User,
    consultation_id: int,
    offset: int,
    limit: int,
):
    # Checks that this consultation belongs to the current vet
    # and their active clinic before accessing the patient's results.
    consultation = get_consultation(
        db, current_user, consultation_id
    )

    statement = (
        select(AIAnalysisResult)
        .join(
            DentalImage,
            DentalImage.dental_image_id
            == AIAnalysisResult.dental_image_id,
        )
        .where(
            DentalImage.pet_id == consultation["pet_id"],
        )
        .options(
            selectinload(AIAnalysisResult.predictions),
        )
        .order_by(
            AIAnalysisResult.analysis_date.desc(),
            AIAnalysisResult.analysis_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return db.scalars(statement).all()

def list_patient_consultation_history(
    db: Session,
    current_user: User,
    consultation_id: int,
    offset: int,
    limit: int,
):
    # Authorize access through the vet's current consultation.
    current = get_consultation(
        db,
        current_user,
        consultation_id,
    )

    statement = (
        select(Consultation)
        .where(
            Consultation.pet_id == current["pet_id"],
            Consultation.clinic_id == current["clinic_id"],
            Consultation.consultation_id != consultation_id,
            Consultation.status == "completed",
            Consultation.consultation_date
            <= current["consultation_date"],
        )
        .options(
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
        .limit(limit)
    )

    records = db.scalars(statement).all()

    return [
        {
            "consultation_id": item.consultation_id,
            "consultation_date": item.consultation_date,
            "veterinarian_name": (
                item.veterinarian.user.full_name
            ),
            "consultation_information": (
                item.consultation_information
            ),
            "examination_findings": item.examination_findings,
            "diagnosis": item.diagnosis,
            "notes": item.notes,
            "treatments": sorted(
                item.treatments,
                key=lambda treatment: treatment.treatment_id,
            ),
            "prescriptions": sorted(
                item.prescriptions,
                key=lambda prescription: (
                    prescription.prescription_id
                ),
            ),
        }
        for item in records
    ]