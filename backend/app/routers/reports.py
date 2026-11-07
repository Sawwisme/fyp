from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.services.report_service import build_report, report_options
from typing import Literal

router=APIRouter(prefix='/reports',tags=['Reports'])


@router.get('')
def report(date_from: date | None=None,date_to: date | None=None,
           report_type: Literal['overview','appointments','consultations','treatments','prescriptions','followups','collections','orders']='overview',
           status: str | None=Query(None,max_length=30),
           veterinarian_id: int | None=Query(None,ge=1,le=2147483647),
           payment_method: str | None=Query(None,max_length=30),
           payment_source: str | None=Query(None,max_length=30),
           shipping_method: str | None=Query(None,max_length=20),
           medication: str | None=Query(None,max_length=100),
           user: User=Depends(require_roles('clinic_administrator','veterinarian')),
           db: Session=Depends(get_db)):
    return build_report(db,user,date_from,date_to,report_type,status,veterinarian_id,
                        payment_method,payment_source,shipping_method,medication)


@router.get('/filters')
def filters(user: User=Depends(require_roles('clinic_administrator','veterinarian')),
            db: Session=Depends(get_db)):
    return report_options(db,user)
