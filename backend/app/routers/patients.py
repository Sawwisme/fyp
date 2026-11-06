from typing import Literal
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.services import patient_service

router = APIRouter(prefix='/vet-patients', tags=['Vet patients'])


@router.get('')
def list_patients(search: str | None = Query(None, max_length=100),
                  offset: int = Query(0, ge=0, le=2147483647),
                  limit: int = Query(20, ge=1, le=100),
                  user: User = Depends(require_roles('veterinarian')),
                  db: Session = Depends(get_db)):
    return patient_service.list_patients(db, user, search, offset, limit)


@router.get('/{pet_id}/records')
def patient_records(pet_id: int = Path(ge=1, le=2147483647),
                    kind: Literal['appointments', 'consultations', 'treatments', 'prescriptions', 'followups'] = 'consultations',
                    offset: int = Query(0, ge=0, le=2147483647),
                    limit: int = Query(20, ge=1, le=100),
                    user: User = Depends(require_roles('veterinarian')),
                    db: Session = Depends(get_db)):
    return patient_service.patient_records(db, user, pet_id, kind, offset, limit)
