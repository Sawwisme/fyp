from fastapi import FastAPI

from app.routers.auth import router as auth_router
from app.routers.pets import router as pets_router
from app.routers.owners import router as owners_router


app = FastAPI(
    title="Veterinary Dental Care System API",
    version="1.0.0",
)

app.include_router(auth_router)
app.include_router(pets_router)
app.include_router(owners_router)


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