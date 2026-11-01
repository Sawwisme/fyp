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