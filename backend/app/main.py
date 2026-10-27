from fastapi import FastAPI
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
from threading import Event, Thread

from app.automatic_scheduling_worker import run_worker
from fastapi.staticfiles import StaticFiles

#router import
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
from app.routers.automatic_scheduling import router as automatic_scheduling_router
from app.routers.clinic_customers import router as clinic_customers_router
from app.routers.clinic_appointments import router as clinic_appointments_router
from app.routers.owner_appointments import router as owner_appointments_router
from app.routers.emergency_requests import router as emergency_requests_router
from app.routers.consultations import router as consultations_router
from app.routers.followups import router as followups_router
from app.routers.treatment_progress import router as treatment_progress_router
from app.routers.return_visits import router as return_visits_router
from app.routers.owner_medical_history import router as owner_medical_history_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = Event()

    worker = Thread(
        target=run_worker,
        args=(stop_event,),
        name="automatic-scheduling",
        daemon=True,
    )

    worker.start()

    try:
        yield
    finally:
        stop_event.set()
        await asyncio.to_thread(worker.join)

app = FastAPI(
    title="Veterinary Dental Care System API",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(automatic_scheduling_router)
app.include_router(clinic_customers_router)
app.include_router(clinic_appointments_router)
app.include_router(owner_appointments_router)
app.include_router(emergency_requests_router)
app.include_router(consultations_router)
app.include_router(followups_router)
app.include_router(treatment_progress_router)
app.include_router(return_visits_router)
app.include_router(owner_medical_history_router)

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