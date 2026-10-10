import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

if len(JWT_SECRET_KEY.encode("utf-8")) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY must contain at least 32 bytes. "
        "Generate a secret and save it in backend/.env."
    )

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "veterinary-dental-care-api"
JWT_AUDIENCE = "veterinary-dental-care-clients"

try:
    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )
except ValueError as exc:
    raise RuntimeError(
        "ACCESS_TOKEN_EXPIRE_MINUTES must be an integer."
    ) from exc

if not 1 <= ACCESS_TOKEN_EXPIRE_MINUTES <= 1440:
    raise RuntimeError(
        "ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440."
    )