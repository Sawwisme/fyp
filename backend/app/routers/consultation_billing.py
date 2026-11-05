from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.consultation_billing import (
    BillDraftCreate,
    BillDraftUpdate,
    BillResponse,
    BillIssue,
    BillingConsultationList,
    BillCashCollect,
    BillCashReceipt,
    BillPaymentSummary,
)
from app.services import consultation_billing_service, billing_workflow_service, billing_cash_service


router = APIRouter(
    prefix="/clinic-billing",
    tags=["Clinic Consultation Billing"],
)


@router.post(
    "/consultations/{consultation_id}/draft",
    response_model=BillResponse,
)
def create_draft(
    data: BillDraftCreate,
    consultation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return consultation_billing_service.create_draft(
        db, current_user, consultation_id, data
    )


@router.get(
    "/consultations/{consultation_id}/bill",
    response_model=BillResponse,
)
def get_bill(
    consultation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return consultation_billing_service.get_bill(
        db, current_user, consultation_id
    )


@router.put(
    "/consultations/{consultation_id}/draft",
    response_model=BillResponse,
)
def update_draft(
    data: BillDraftUpdate,
    consultation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return consultation_billing_service.update_draft(
        db, current_user, consultation_id, data
    )

@router.get(
    "/consultations",
    response_model=BillingConsultationList,
)
def list_billing_consultations(
    q: str = Query(default="", max_length=100),
    bill_status: Literal[
        "unbilled",
        "draft",
        "issued",
        "paid",
        "void",
    ] | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return billing_workflow_service.list_billing_consultations(
        db,
        current_user,
        q,
        bill_status,
        offset,
        limit,
    )


@router.post(
    "/consultations/{consultation_id}/issue",
    response_model=BillResponse,
)
def issue_bill(
    data: BillIssue,
    consultation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return billing_workflow_service.issue_bill(
        db,
        current_user,
        consultation_id,
        data,
    )

@router.post(
    "/consultations/{consultation_id}/collect-cash",
    response_model=BillCashReceipt,
)
def collect_cash(
    data: BillCashCollect,
    consultation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return billing_cash_service.collect_cash(
        db,
        current_user,
        consultation_id,
        data,
    )

@router.get(
    "/consultations/{consultation_id}/payments",
    response_model=list[BillPaymentSummary],
)
def list_bill_payments(
    consultation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return billing_cash_service.list_bill_payments(
        db,
        current_user,
        consultation_id,
    )