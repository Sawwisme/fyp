from fastapi import FastAPI

app = FastAPI(
    title="Veterinary Dental Care System API",
    version="1.0.0"
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