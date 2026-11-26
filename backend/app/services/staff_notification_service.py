"""Staff notifications saved within their originating transaction."""
from sqlalchemy import select
from app.models import Notification, User, Veterinarian, ClinicAdministrator, Pet


def _add(db, user_id, event_key, title, message, resource_type, resource_id):
    if user_id is None:
        return
    if any(isinstance(row, Notification) and row.user_id == user_id
           and row.event_key == event_key for row in db.new):
        return
    if db.scalar(select(Notification.notification_id).where(
        Notification.user_id == user_id, Notification.event_key == event_key)):
        return
    db.add(Notification(user_id=user_id, event_key=event_key,
        notification_type=resource_type, title=title, message=message,
        resource_type=resource_type, resource_id=resource_id))


def _vet_user(db, vet_id):
    return db.scalar(select(Veterinarian.user_id).join(User,
        User.user_id == Veterinarian.user_id).where(
        Veterinarian.veterinarian_id == vet_id,
        Veterinarian.approval_status == "approved", User.status == "active",
        User.role == "veterinarian"))


def notify_booking_confirmed(db, appointment):
    if appointment.status != "confirmed":
        return
    pet = db.get(Pet, appointment.pet_id)
    name = pet.pet_name if pet else "a patient"
    attached = " An AI assessment is attached for reference." if appointment.ai_analysis_id else ""
    _add(db, _vet_user(db, appointment.veterinarian_id),
        f"staff-booking:{appointment.appointment_id}:confirmed",
        "Appointment confirmed",
        f"Appointment #{appointment.appointment_id} for {name} on {appointment.appointment_date} is confirmed." + attached,
        "staff_appointment", appointment.appointment_id)


def notify_emergency_requested(db, request):
    recipients = db.scalars(select(ClinicAdministrator.user_id).join(User,
        User.user_id == ClinicAdministrator.user_id).where(
        ClinicAdministrator.clinic_id == request.clinic_id,
        ClinicAdministrator.membership_status == "approved",
        User.status == "active", User.role == "clinic_administrator")).all()
    for user_id in set(recipients):
        _add(db, user_id, f"staff-emergency:{request.emergency_appointment_id}:requested",
            "Emergency request awaiting review",
            f"Request #{request.emergency_appointment_id} needs clinic review. Open the schedule to assess and respond; urgency has not been confirmed.",
            "staff_emergency", request.emergency_appointment_id)


def notify_followup_submitted(db, followup, submission):
    pet = db.get(Pet, followup.pet_id)
    name = pet.pet_name if pet else "a patient"
    _add(db, _vet_user(db, followup.veterinarian_id),
        f"staff-followup:{submission.submission_id}:submitted",
        "Follow-up update awaiting review",
        f"A new update for {name}, follow-up #{followup.followup_care_id}, is ready for your review.",
        "staff_followup", followup.followup_care_id)
