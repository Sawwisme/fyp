from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.emergency_requests import (
    EmergencyRequestCreate,
    EmergencyRequestResponse,
    EmergencyRequestListItem,
    EmergencyRequestApprove,
    EmergencyRequestReject,
)
from app.services import emergency_request_service


router = APIRouter(
    prefix="/emergency-requests",
    tags=["Emergency Requests"],
)

RequestStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "cancelled",
]


@router.post(
    "",
    response_model=EmergencyRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_request(
    data: EmergencyRequestCreate,
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return emergency_request_service.create_request(
        db, current_user, data
    )


@router.get(
    "/mine",
    response_model=list[EmergencyRequestListItem],
)
def get_my_requests(
    request_status: RequestStatus | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return emergency_request_service.list_my_requests(
        db, current_user, request_status, offset, limit
    )


@router.get(
    "/clinic",
    response_model=list[EmergencyRequestListItem],
)
def get_clinic_requests(
    request_status: RequestStatus | None = "pending",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return emergency_request_service.list_clinic_requests(
        db, current_user, request_status, offset, limit
    )

@router.post(
    "/{request_id}/approve",
    response_model=EmergencyRequestResponse,
)
def approve_request(
    data: EmergencyRequestApprove,
    request_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return emergency_request_service.approve_request(
        db, current_user, request_id, data
    )

@router.post(
    "/{request_id}/reject",
    response_model=EmergencyRequestResponse,
)
def reject_request(
    data: EmergencyRequestReject,
    request_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return emergency_request_service.reject_request(
        db, current_user, request_id, data
    )

@router.post(
    "/{request_id}/cancel",
    response_model=EmergencyRequestResponse,
)
def cancel_my_request(
    request_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("pet_owner")
    ),
    db: Session = Depends(get_db),
):
    return emergency_request_service.cancel_my_request(
        db, current_user, request_id
    )