import os
from pathlib import Path

from dotenv import load_dotenv
from urllib.parse import urlsplit


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

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")

try:
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
except ValueError as exc:
    raise RuntimeError("SMTP_PORT must be an integer.") from exc

if not 1 <= SMTP_PORT <= 65535:
    raise RuntimeError("SMTP_PORT must be between 1 and 65535.")

RESET_PAGE_URL = os.getenv(
    "RESET_PAGE_URL",
    "http://127.0.0.1:8000/auth/reset-password",
)

reset_url = urlsplit(RESET_PAGE_URL)

if (
    not reset_url.hostname
    or reset_url.username
    or reset_url.password
    or reset_url.query
    or reset_url.fragment
    or reset_url.path != "/auth/reset-password"
):
    raise RuntimeError("RESET_PAGE_URL must point to /auth/reset-password.")

local_http = (
    reset_url.scheme == "http"
    and reset_url.hostname in {"127.0.0.1", "localhost"}
)

if reset_url.scheme != "https" and not local_http:
    raise RuntimeError(
        "RESET_PAGE_URL requires HTTPS, except for local development."
    )