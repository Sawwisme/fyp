from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    ClinicAdministrator,
    Notification,
    PetOwner,
    User,
    VeterinarianAbsence,
    Consultation,
    DentalImage,
    Pet,
)
from app.schemas.notifications import NotificationResponse


def list_my_notifications(
    db: Session,
    current_user: User,
    unread_only: bool,
    offset: int,
    limit: int,
):
    statement = select(Notification).where(
        Notification.user_id == current_user.user_id,
    )

    if unread_only:
        statement = statement.where(
            Notification.read_at.is_(None),
        )

    return db.scalars(
        statement
        .order_by(
            Notification.created_at.desc(),
            Notification.notification_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()


def get_my_unread_count(
    db: Session,
    current_user: User,
):
    count = db.scalar(
        select(func.count(Notification.notification_id))
        .where(
            Notification.user_id == current_user.user_id,
            Notification.read_at.is_(None),
        )
    )

    return {"unread_count": int(count or 0)}


def mark_as_read(
    db: Session,
    current_user: User,
    notification_id: int,
):
    try:
        notification = db.scalar(
            select(Notification)
            .where(
                Notification.notification_id == notification_id,
                Notification.user_id == current_user.user_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if notification is None:
            raise HTTPException(404, "Notification not found.")

        # Preserve the first time this notification was read.
        if notification.read_at is None:
            notification.read_at = datetime.now(
                timezone.utc
            ).replace(tzinfo=None)

        db.flush()

        result = NotificationResponse.model_validate(notification)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise

def notify_absence_reported(
    db: Session,
    absence: VeterinarianAbsence,
    veterinarian_name: str,
    appointments: list[Appointment],
):
    if not appointments:
        return

    date_label = absence.absence_date.strftime("%d/%m/%Y")
    time_label = (
        f"{absence.start_time.strftime('%H:%M')}–"
        f"{absence.end_time.strftime('%H:%M')}"
    )

    admin_user_ids = db.scalars(
        select(ClinicAdministrator.user_id)
        .join(
            User,
            User.user_id == ClinicAdministrator.user_id,
        )
        .where(
            ClinicAdministrator.clinic_id == absence.clinic_id,
            ClinicAdministrator.membership_status == "approved",
            User.role == "clinic_administrator",
            User.status == "active",
        )
    ).all()

    for user_id in admin_user_ids:
        db.add(
            Notification(
                user_id=user_id,
                event_key=f"absence:{absence.absence_id}:admin",
                notification_type="absence_appointments_affected",
                title="Appointments need rearrangement",
                message=(
                    f"{veterinarian_name} reported absence on "
                    f"{date_label}, {time_label}. "
                    f"{len(appointments)} appointment(s) are affected. "
                    "Contact the owners to arrange alternatives."
                ),
                resource_type="clinic_rearrangements",
                resource_id=absence.absence_id,
            )
        )

    owner_ids = {
        appointment.pet_owner_id
        for appointment in appointments
    }

    owner_accounts = dict(
        db.execute(
            select(
                PetOwner.pet_owner_id,
                PetOwner.user_id,
            )
            .join(
                User,
                User.user_id == PetOwner.user_id,
            )
            .where(
                PetOwner.pet_owner_id.in_(owner_ids),
                User.role == "pet_owner",
                User.status == "active",
            )
        ).all()
    )

    for appointment in appointments:
        owner_user_id = owner_accounts.get(
            appointment.pet_owner_id
        )

        # Walk-in owners may not have an app account.
        if owner_user_id is None:
            continue

        db.add(
            Notification(
                user_id=owner_user_id,
                event_key=(
                    f"absence:{absence.absence_id}:"
                    f"appointment:{appointment.appointment_id}"
                ),
                notification_type="appointment_rearrangement_required",
                title="Your appointment needs rearrangement",
                message=(
                    f"The veterinarian for appointment "
                    f"#{appointment.appointment_id} on {date_label} "
                    "is unavailable. Your booking has not been "
                    "automatically cancelled. Please contact the "
                    "clinic to arrange another time or veterinarian."
                ),
                resource_type="appointment",
                resource_id=appointment.appointment_id,
            )
        )

    # Do not commit here. The calling service owns the transaction.

def notify_emergency_approved(db, request):
    if (
        request.approval_status != "approved"
        or request.appointment_id is None
    ):
        raise ValueError(
            "Emergency approval notification requires an appointment."
        )

    user_id = db.scalar(
        select(PetOwner.user_id)
        .join(User, User.user_id == PetOwner.user_id)
        .where(
            PetOwner.pet_owner_id == request.pet_owner_id,
            User.role == "pet_owner",
            User.status == "active",
        )
    )

    if user_id is None:
        return

    event_key = (
        f"emergency:{request.emergency_appointment_id}:approved"
    )

    existing = db.scalar(
        select(Notification.notification_id).where(
            Notification.user_id == user_id,
            Notification.event_key == event_key,
        )
    )

    if existing is not None:
        return

    db.add(
        Notification(
            user_id=user_id,
            event_key=event_key,
            notification_type="emergency_request_approved",
            title="Emergency appointment confirmed",
            message=(
                "Your clinic approved emergency request "
                f"#{request.emergency_appointment_id}. "
                f"Appointment #{request.appointment_id} is confirmed. "
                "Open the appointment to check its time and veterinarian."
            ),
            resource_type="appointment",
            resource_id=request.appointment_id,
        )
    )

    # The approval service commits the appointment and notification together.

def notify_emergency_rejected(db, request):
    if request.approval_status != "rejected":
        raise ValueError("Emergency request must be rejected.")

    user_id = db.scalar(
        select(PetOwner.user_id)
        .join(User, User.user_id == PetOwner.user_id)
        .where(
            PetOwner.pet_owner_id == request.pet_owner_id,
            User.role == "pet_owner",
            User.status == "active",
        )
    )

    if user_id is None:
        return

    event_key = f"emergency:{request.emergency_appointment_id}:rejected"

    if db.scalar(
        select(Notification.notification_id).where(
            Notification.user_id == user_id,
            Notification.event_key == event_key,
        )
    ) is not None:
        return

    db.add(Notification(
        user_id=user_id,
        event_key=event_key,
        notification_type="emergency_request_rejected",
        title="Emergency request not accepted",
        message=(
            f"Your clinic did not accept emergency request "
            f"#{request.emergency_appointment_id}. "
            "Open the request to read the clinic's reason. "
            "This does not mean it is safe to delay veterinary care."
        ),
        resource_type="emergency_request",
        resource_id=request.emergency_appointment_id,
    ))

def notify_followup_reviewed(db, followup, submission, decision):
    messages = {
        "complete": (
            "Follow-up review completed",
            "Your veterinarian completed this follow-up review.",
        ),
        "request_update": (
            "Another follow-up update requested",
            "Your veterinarian requested another progress update.",
        ),
        "in_clinic": (
            "Clinic visit recommended",
            "Your veterinarian recommended an in-clinic review.",
        ),
    }

    if decision.outcome not in messages:
        raise ValueError("Unsupported follow-up review outcome.")

    recipient = db.execute(
        select(PetOwner.user_id, Appointment.appointment_id)
        .select_from(Appointment)
        .join(
            Consultation,
            Consultation.appointment_id == Appointment.appointment_id,
        )
        .join(
            PetOwner,
            PetOwner.pet_owner_id == Appointment.pet_owner_id,
        )
        .join(User, User.user_id == PetOwner.user_id)
        .where(
            Consultation.consultation_id == followup.consultation_id,
            Consultation.status == "completed",
            Appointment.pet_id == followup.pet_id,
            PetOwner.pet_owner_id == submission.pet_owner_id,
            User.role == "pet_owner",
            User.status == "active",
        )
    ).first()

    if recipient is None:
        return

    user_id, appointment_id = recipient
    event_key = f"followup-review:{decision.decision_id}"

    if db.scalar(
        select(Notification.notification_id).where(
            Notification.user_id == user_id,
            Notification.event_key == event_key,
        )
    ) is not None:
        return

    title, description = messages[decision.outcome]

    if decision.correction_reason:
        title = "Follow-up review updated"

    db.add(Notification(
        user_id=user_id,
        event_key=event_key,
        notification_type="followup_reviewed",
        title=title,
        message=(
            f"{description} Follow-up #{followup.followup_care_id}. "
            "Open the appointment, then View updates to read "
            "the recorded feedback and instructions."
        ),
        resource_type="appointment",
        resource_id=appointment_id,
    ))

def notify_assessment_finished(db, job):
    messages = {
        "completed": (
            "Dental assessment ready",
            "Your AI dental assessment is ready. "
            "Open it to view the screening result and its limitations.",
        ),
        "rejected": (
            "Dental photo needs attention",
            "Your photo did not pass assessment validation. "
            "Open the assessment to read the reason.",
        ),
        "failed": (
            "Dental assessment could not finish",
            "Your assessment could not be completed. "
            "Open it to check the status before trying again.",
        ),
    }

    if job.status not in messages:
        return

    # Notify only the uploader who still owns the image's pet.
    user_id = db.scalar(
        select(User.user_id)
        .select_from(DentalImage)
        .join(Pet, Pet.pet_id == DentalImage.pet_id)
        .join(PetOwner, PetOwner.pet_owner_id == Pet.pet_owner_id)
        .join(User, User.user_id == DentalImage.uploaded_by)
        .where(
            DentalImage.dental_image_id == job.dental_image_id,
            PetOwner.user_id == User.user_id,
            User.role == "pet_owner",
            User.status == "active",
        )
    )

    if user_id is None:
        return

    event_key = f"assessment:{job.assessment_job_id}:{job.status}"

    if db.scalar(
        select(Notification.notification_id).where(
            Notification.user_id == user_id,
            Notification.event_key == event_key,
        )
    ) is not None:
        return

    title, message = messages[job.status]

    db.add(Notification(
        user_id=user_id,
        event_key=event_key,
        notification_type=f"dental_assessment_{job.status}",
        title=title,
        message=message,
        resource_type="dental_assessment",
        resource_id=job.assessment_job_id,
    ))

def get_notification_updates(db, current_user, after_id=None):
    owned = Notification.user_id == current_user.user_id

    # First connection establishes a baseline without replaying old alerts.
    if after_id is None:
        latest = db.scalar(
            select(func.max(Notification.notification_id)).where(owned)
        )
        return {"items": [], "cursor": int(latest or 0)}

    records = db.scalars(
        select(Notification)
        .where(
            owned,
            Notification.notification_id > after_id,
        )
        .order_by(Notification.notification_id.asc())
        .limit(100)
    ).all()

    return {
        "items": [
            NotificationResponse.model_validate(record)
            for record in records
        ],
        "cursor": (
            records[-1].notification_id if records else after_id
        ),
    }

def get_notification_by_id(
    db: Session,
    current_user: User,
    notification_id: int,
):
    notification = db.scalar(
        select(Notification).where(
            Notification.notification_id == notification_id,
            Notification.user_id == current_user.user_id,
        )
    )

    if notification is None:
        raise HTTPException(
            status_code=404,
            detail="Notification not found.",
        )

    return notification
