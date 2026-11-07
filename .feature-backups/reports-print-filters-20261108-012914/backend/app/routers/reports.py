from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.services.report_service import build_report

router=APIRouter(prefix='/reports',tags=['Reports'])


@router.get('')
def report(date_from: date | None=None,date_to: date | None=None,
           user: User=Depends(require_roles('clinic_administrator','veterinarian')),
           db: Session=Depends(get_db)):
    return build_report(db,user,date_from,date_to)
