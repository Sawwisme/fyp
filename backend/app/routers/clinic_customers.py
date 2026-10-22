from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.clinic_customers import (
    ClinicCustomerResponse,
    WalkInCustomerCreate,
)
from app.services import clinic_customer_service


router = APIRouter(
    prefix="/clinic-customers",
    tags=["Clinic Customers"],
)


@router.get(
    "",
    response_model=list[ClinicCustomerResponse],
)
def search_customers(
    q: str = Query(min_length=2, max_length=150),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_customer_service.search_customers(
        db,
        current_user,
        q,
        offset,
        limit,
    )


@router.post(
    "",
    response_model=ClinicCustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer(
    data: WalkInCustomerCreate,
    current_user: User = Depends(
        require_roles("clinic_administrator")
    ),
    db: Session = Depends(get_db),
):
    return clinic_customer_service.create_customer(
        db,
        current_user,
        data,
    )