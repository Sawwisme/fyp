from fastapi import APIRouter, Query

from app.schemas.clinic_discovery import DiscoveredClinic
from app.services import clinic_discovery_service


router = APIRouter(
    prefix="/clinic-discovery",
    tags=["Clinic Map Search"],
)


@router.get(
    "/search",
    response_model=list[DiscoveredClinic],
)
def search_clinics(
    latitude: float = Query(
        ge=-90,
        le=90,
        allow_inf_nan=False,
    ),
    longitude: float = Query(
        ge=-180,
        le=180,
        allow_inf_nan=False,
    ),
):
    return clinic_discovery_service.search_clinics(
        latitude,
        longitude,
    )

@router.get(
    "/by-name",
    response_model=list[DiscoveredClinic],
)
def search_clinics_by_name(
    q: str = Query(min_length=3, max_length=150),
):
    return clinic_discovery_service.search_clinics_by_name(q)