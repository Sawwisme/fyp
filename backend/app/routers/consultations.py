from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.consultations import (
    ConsultationResponse,
    ConsultationSave,
    ConsultationSummary,
    TreatmentHistoryItem,
    PrescriptionHistoryItem,
    ConsultationCounts,
    ConsultationAssessment,
    PatientConsultationHistory,
    ClinicalHistoryCounts,
)
from app.services import consultation_service


router = APIRouter(
    prefix="/consultations",
    tags=["Consultations"],
)


@router.post(
    "/appointments/{appointment_id}/start",
    response_model=ConsultationResponse,
)
def start_consultation(
    appointment_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return consultation_service.start_consultation(
        db, current_user, appointment_id
    )


@router.get(
    "/{consultation_id}",
    response_model=ConsultationResponse,
)
def get_consultation(
    consultation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return consultation_service.get_consultation(
        db, current_user, consultation_id
    )


@router.put(
    "/{consultation_id}",
    response_model=ConsultationResponse,
)
def save_consultation(
    data: ConsultationSave,
    consultation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return consultation_service.save_consultation(
        db, current_user, consultation_id, data
    )

@router.get(
    "",
    response_model=list[ConsultationSummary],
)
def list_my_consultations(
    search: str | None = Query(default=None, max_length=100),
    consultation_status: Literal["draft", "completed"] | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return consultation_service.list_my_consultations(
        db,
        current_user,
        search,
        consultation_status,
        offset,
        limit,
    )

@router.get(
    "/treatments/history",
    response_model=list[TreatmentHistoryItem],
)
def get_treatment_history(
    search: str | None = Query(default=None, max_length=100),
    consultation_status: Literal["draft", "completed"] | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return consultation_service.list_my_clinical_history(
        db,
        current_user,
        "treatments",
        search,
        consultation_status,
        offset,
        limit,
        date_from=date_from,
        date_to=date_to,
    )

@router.get(
    "/prescriptions/history",
    response_model=list[PrescriptionHistoryItem],
)
def get_prescription_history(
    search: str | None = Query(default=None, max_length=100),
    consultation_status: Literal["draft", "completed"] | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return consultation_service.list_my_clinical_history(
        db,
        current_user,
        "prescriptions",
        search,
        consultation_status,
        offset,
        limit,
        date_from=date_from,
        date_to=date_to,
    )

@router.get(
    "/summary/counts",
    response_model=ConsultationCounts,
)
def get_consultation_counts(
    search: str | None = Query(default=None, max_length=100),
    consultation_status: Literal["draft", "completed"] | None = None,
    current_user: User = Depends(require_roles("veterinarian")),
    db: Session = Depends(get_db),
):
    return consultation_service.list_my_consultations(
        db,
        current_user,
        search,
        consultation_status,
        0,
        1,
        counts_only=True,
    )

@router.get(
    "/{consultation_id}/ai-assessments",
    response_model=list[ConsultationAssessment],
)
def list_consultation_assessments(
    consultation_id: int = Path(ge=1, le=2147483647),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return consultation_service.list_consultation_assessments(
        db,
        current_user,
        consultation_id,
        offset,
        limit,
    )

@router.get(
    "/{consultation_id}/patient-history",
    response_model=list[PatientConsultationHistory],
)
def list_patient_consultation_history(
    consultation_id: int = Path(ge=1, le=2147483647),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return consultation_service.list_patient_consultation_history(
        db,
        current_user,
        consultation_id,
        offset,
        limit,
    )

@router.get(
    "/clinical-history/counts",
    response_model=ClinicalHistoryCounts,
)
def get_clinical_history_counts(
    record_type: Literal[
        "treatments", "prescriptions"
    ] = "treatments",
    search: str | None = Query(default=None, max_length=100),
    consultation_status: Literal[
        "draft", "completed"
    ] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(
        require_roles("veterinarian")
    ),
    db: Session = Depends(get_db),
):
    return consultation_service.list_my_clinical_history(
        db,
        current_user,
        record_type,
        search,
        consultation_status,
        0,
        1,
        date_from=date_from,
        date_to=date_to,
        counts_only=True,
    )