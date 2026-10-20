from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.admin_registration import (
    AdminRegistrationRequest,
    RegistrationClinicOption,
)
from app.schemas.auth import MessageResponse
from app.services import admin_registration_service


router = APIRouter(
    prefix="/admin-registration",
    tags=["Administrator Registration"],
)


@router.get(
    "/clinics",
    response_model=list[RegistrationClinicOption],
)
def list_available_clinics(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return admin_registration_service.list_registration_clinics(
        db,
        offset,
        limit,
    )


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_administrator(
    data: AdminRegistrationRequest,
    db: Session = Depends(get_db),
):
    admin_registration_service.register_administrator(db, data)

    return MessageResponse(
        message=(
            "Your clinic and administrator account have been created. "
            "You can now sign in using Clinic Administrator."
        ),
    )