from fastapi import FastAPI
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from app.routers.auth import router as auth_router
from app.routers.pets import router as pets_router
from app.routers.owners import router as owners_router
from app.routers.availability import router as availability_router
from app.routers.admins import router as admins_router
from app.routers.staff import router as staff_router
from app.routers.veterinarians import router as veterinarians_router
from app.routers.schedules import router as schedules_router
from app.routers.clinics import router as clinics_router
from app.routers.admin_registration import router as admin_registration_router
from app.routers.clinic_discovery import router as clinic_discovery_router

app = FastAPI(
    title="Veterinary Dental Care System API",
    version="1.0.0",
)

app.include_router(auth_router)
app.include_router(pets_router)
app.include_router(owners_router)
app.include_router(availability_router)
app.include_router(admins_router)
app.include_router(staff_router)
app.include_router(veterinarians_router)
app.include_router(schedules_router)
app.include_router(clinics_router)
app.include_router(admin_registration_router)
app.include_router(clinic_discovery_router)

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

app.mount(
    "/web",
    StaticFiles(directory=str(WEB_DIR), html=True),
    name="web",
)


@app.get("/")
def root():
    return {
        "message": "Veterinary Dental Care System API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }