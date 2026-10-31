from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Clinic,
    EmergencyAppointment,
    Pet,
    PetOwner,
    User,
    Appointment, 
    Schedule, 
    TimeSlot, 
    Veterinarian,
)

from app.schemas.emergency_requests import EmergencyRequestCreate
from app.services.admin_profile_service import get_admin_record
from app.services.pet_service import get_owner_profile
from app.clinic_time import CLINIC_TIMEZONE
from app.services.schedule_service import (
    lock_schedule,
    reject_occupied_slots,
)

from app.services.vet_absence_service import reject_absent_slots


def create_request(
    db: Session,
    current_user: User,
    data: EmergencyRequestCreate,
):
    try:
        owner = get_owner_profile(db, current_user)

        clinic = db.scalar(
            select(Clinic)
            .where(
                Clinic.clinic_id == data.clinic_id,
                Clinic.status == "active",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(
                404, "This clinic is unavailable."
            )

        pet = db.scalar(
            select(Pet)
            .where(
                Pet.pet_id == data.pet_id,
                Pet.pet_owner_id == owner.pet_owner_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if pet is None:
            raise HTTPException(
                404, "Pet not found in your account."
            )

        # Serialize submissions using the clinic and pet locks,
        # then check whether a pending request already exists.
        pending = db.scalar(
            select(EmergencyAppointment.emergency_appointment_id)
            .where(
                EmergencyAppointment.clinic_id == clinic.clinic_id,
                EmergencyAppointment.pet_id == pet.pet_id,
                EmergencyAppointment.approval_status == "pending",
            )
            .limit(1)
            .with_for_update()
        )

        if pending is not None:
            raise HTTPException(
                409,
                "This pet already has a pending request at this clinic.",
            )

        request = EmergencyAppointment(
            clinic_id=clinic.clinic_id,
            pet_owner_id=owner.pet_owner_id,
            pet_id=pet.pet_id,
            emergency_reason=data.emergency_reason,
            urgency_level="unassessed",
            approval_status="pending",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        db.add(request)
        db.commit()
        db.refresh(request)

        return request

    except Exception:
        db.rollback()
        raise


def _list_requests(
    db: Session,
    statement,
    request_status: str | None,
    offset: int,
    limit: int,
):
    if request_status is not None:
        statement = statement.where(
            EmergencyAppointment.approval_status == request_status
        )

    records = db.scalars(
        statement
        .options(
            selectinload(EmergencyAppointment.clinic),
            selectinload(EmergencyAppointment.pet),
            selectinload(EmergencyAppointment.owner)
            .selectinload(PetOwner.user),
        )
        .order_by(
            EmergencyAppointment.created_at.desc(),
            EmergencyAppointment.emergency_appointment_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    result = []

    for record in records:
        owner = record.owner
        user = owner.user

        result.append({
            "emergency_appointment_id":
                record.emergency_appointment_id,
            "clinic_id": record.clinic_id,
            "clinic_name": record.clinic.clinic_name,
            "pet_owner_id": record.pet_owner_id,
            "pet_id": record.pet_id,
            "pet_name": record.pet.pet_name,
            "owner_name": (
                user.full_name if user is not None
                else owner.contact_name or "Not recorded"
            ),
            "owner_phone": (
                user.phone_number if user is not None
                else owner.contact_phone
            ),
            "emergency_reason": record.emergency_reason,
            "urgency_level": record.urgency_level,
            "approval_status": record.approval_status,
            "appointment_id": record.appointment_id,
            "assigned_veterinarian_id":
                record.assigned_veterinarian_id,
            "created_at": record.created_at,
            "reviewed_at": record.reviewed_at,
            "rejection_reason": record.rejection_reason,
        })

    return result


def list_my_requests(
    db: Session,
    current_user: User,
    request_status: str | None,
    offset: int,
    limit: int,
):
    owner = get_owner_profile(db, current_user)

    statement = select(EmergencyAppointment).where(
        EmergencyAppointment.pet_owner_id == owner.pet_owner_id
    )

    return _list_requests(
        db, statement, request_status, offset, limit
    )


def list_clinic_requests(
    db: Session,
    current_user: User,
    request_status: str | None,
    offset: int,
    limit: int,
):
    administrator = get_admin_record(db, current_user)

    statement = select(EmergencyAppointment).where(
        EmergencyAppointment.clinic_id == administrator.clinic_id
    )

    return _list_requests(
        db, statement, request_status, offset, limit
    )

def _lock_pending_request(
    db: Session,
    current_user: User,
    request_id: int,
):
    administrator = get_admin_record(db, current_user)

    # All request decisions first lock the clinic.
    clinic = db.scalar(
        select(Clinic)
        .where(
            Clinic.clinic_id == administrator.clinic_id,
            Clinic.status == "active",
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if clinic is None:
        raise HTTPException(403, "Your clinic is not active.")

    request = db.scalar(
        select(EmergencyAppointment)
        .where(
            EmergencyAppointment.emergency_appointment_id
            == request_id,
            EmergencyAppointment.clinic_id == clinic.clinic_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if request is None:
        raise HTTPException(
            404, "Emergency request not found in your clinic."
        )

    if (
        request.approval_status != "pending"
        or request.appointment_id is not None
    ):
        raise HTTPException(
            409, "This request has already been handled."
        )

    return administrator, request


def approve_request(
    db: Session,
    current_user: User,
    request_id: int,
    data,
):
    try:
        administrator, request = _lock_pending_request(
            db, current_user, request_id
        )

        schedule_id = db.scalar(
            select(TimeSlot.schedule_id).where(
                TimeSlot.time_slot_id == data.time_slot_id
            )
        )

        if schedule_id is None:
            raise HTTPException(404, "Appointment slot not found.")

        schedule = lock_schedule(db, schedule_id, current_user)

        eligible_vet = db.scalar(
            select(Veterinarian.veterinarian_id)
            .join(Veterinarian.user)
            .where(
                Veterinarian.veterinarian_id
                == schedule.veterinarian_id,
                Veterinarian.clinic_id == request.clinic_id,
                Veterinarian.approval_status == "approved",
                User.role == "veterinarian",
                User.status == "active",
            )
            .with_for_update()
        )

        if eligible_vet is None:
            raise HTTPException(
                409, "This veterinarian is unavailable."
            )

        slot = db.scalar(
            select(TimeSlot)
            .where(
                TimeSlot.time_slot_id == data.time_slot_id,
                TimeSlot.schedule_id == schedule.schedule_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if (
            slot is None
            or slot.status != "available"
            or schedule.status != "active"
        ):
            raise HTTPException(
                409, "This slot is no longer available."
            )

        if (
            slot.end_time <= slot.start_time
            or slot.start_time < schedule.start_time
            or slot.end_time > schedule.end_time
        ):
            raise HTTPException(
                409, "This slot has invalid working hours."
            )

        end = datetime.combine(
            schedule.schedule_date,
            slot.end_time,
            tzinfo=CLINIC_TIMEZONE,
        )

        # Emergency bookings can use a currently running slot,
        # but never a slot that has already ended.
        if end <= datetime.now(CLINIC_TIMEZONE):
            raise HTTPException(
                400, "Choose a slot that has not ended."
            )
        reject_absent_slots(db, [slot.time_slot_id])
        reject_occupied_slots(db, [slot.time_slot_id])

        pet = db.scalar(
            select(Pet)
            .where(
                Pet.pet_id == request.pet_id,
                Pet.pet_owner_id == request.pet_owner_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if pet is None:
            raise HTTPException(
                409, "The pet no longer belongs to this owner."
            )

        overlapping = db.scalar(
            select(Appointment.appointment_id)
            .join(
                TimeSlot,
                TimeSlot.time_slot_id == Appointment.time_slot_id,
            )
            .join(
                Schedule,
                Schedule.schedule_id == TimeSlot.schedule_id,
            )
            .where(
                Appointment.pet_id == request.pet_id,
                Appointment.status.notin_(["cancelled", "rejected"]),
                Schedule.schedule_date == schedule.schedule_date,
                TimeSlot.start_time < slot.end_time,
                TimeSlot.end_time > slot.start_time,
            )
            .limit(1)
            .with_for_update()
        )

        if overlapping is not None:
            raise HTTPException(
                409,
                "This pet already has an overlapping appointment.",
            )

        appointment = Appointment(
            pet_owner_id=request.pet_owner_id,
            pet_id=request.pet_id,
            veterinarian_id=schedule.veterinarian_id,
            time_slot_id=slot.time_slot_id,
            appointment_date=schedule.schedule_date,
            appointment_type="emergency",
            appointment_source="emergency",
            created_by_user_id=current_user.user_id,
            status="confirmed",
        )

        slot.status = "booked"
        db.add(appointment)
        db.flush()

        request.appointment_id = appointment.appointment_id
        request.assigned_veterinarian_id = schedule.veterinarian_id
        request.approved_by = administrator.clinic_administrator_id
        request.urgency_level = data.urgency_level
        request.approval_status = "approved"
        request.reviewed_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        )
        request.rejection_reason = None

        db.commit()
        db.refresh(request)

        return request

    except Exception:
        db.rollback()
        raise


def reject_request(
    db: Session,
    current_user: User,
    request_id: int,
    data,
):
    try:
        administrator, request = _lock_pending_request(
            db, current_user, request_id
        )

        request.approval_status = "rejected"
        request.rejection_reason = data.rejection_reason
        request.approved_by = administrator.clinic_administrator_id
        request.reviewed_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        )

        db.commit()
        db.refresh(request)

        return request

    except Exception:
        db.rollback()
        raise

def cancel_my_request(
    db: Session,
    current_user: User,
    request_id: int,
):
    try:
        owner = get_owner_profile(db, current_user)

        clinic_id = db.scalar(
            select(EmergencyAppointment.clinic_id)
            .where(
                EmergencyAppointment.emergency_appointment_id
                == request_id,
                EmergencyAppointment.pet_owner_id
                == owner.pet_owner_id,
            )
        )

        if clinic_id is None:
            raise HTTPException(404, "Emergency request not found.")

        # Use the same clinic lock as admin approval/rejection.
        # Owners may cancel even if the clinic became inactive.
        clinic = db.scalar(
            select(Clinic)
            .where(Clinic.clinic_id == clinic_id)
            .with_for_update()
        )

        if clinic is None:
            raise HTTPException(404, "Clinic not found.")

        request = db.scalar(
            select(EmergencyAppointment)
            .where(
                EmergencyAppointment.emergency_appointment_id
                == request_id,
                EmergencyAppointment.pet_owner_id
                == owner.pet_owner_id,
                EmergencyAppointment.clinic_id == clinic_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if request is None:
            raise HTTPException(404, "Emergency request not found.")

        if request.approval_status == "cancelled":
            db.commit()
            db.refresh(request)
            return request

        if (
            request.approval_status != "pending"
            or request.appointment_id is not None
        ):
            raise HTTPException(
                409,
                "This request has already been handled. "
                "Refresh to see its latest status.",
            )

        request.approval_status = "cancelled"

        db.commit()
        db.refresh(request)

        return request

    except Exception:
        db.rollback()
        raise