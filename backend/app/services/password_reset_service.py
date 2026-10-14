from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import hashlib
import logging
from collections import deque
from threading import Lock
from time import monotonic
from urllib.parse import quote

from app.config import RESET_PAGE_URL
from app.database import SessionLocal
from app.services.email_service import send_email

from app.config import JWT_ALGORITHM, JWT_ISSUER, JWT_SECRET_KEY
from app.models import User
from app.services.auth_service import (
    hash_password,
    password_version,
    token_version_matches,
    verify_password,
)


RESET_AUDIENCE = "veterinary-dental-care-password-reset"
RESET_EXPIRE_MINUTES = 15


def create_reset_token(user: User) -> str:
    now = datetime.now(timezone.utc)

    return jwt.encode(
        {
            "sub": str(user.user_id),
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=RESET_EXPIRE_MINUTES),
            "jti": str(uuid4()),
            "iss": JWT_ISSUER,
            "aud": RESET_AUDIENCE,
            "purpose": "password_reset",
            "pwd_version": password_version(user.password_hash),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def reset_password(
    db: Session,
    token: str,
    new_password: str,
) -> None:
    invalid_token = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="The reset link is invalid or expired. Request a new one.",
    )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=RESET_AUDIENCE,
            options={
                "require": [
                    "sub",
                    "iat",
                    "nbf",
                    "exp",
                    "jti",
                    "iss",
                    "aud",
                    "purpose",
                    "pwd_version",
                ],
            },
        )

        subject = payload["sub"]

        if (
            payload["purpose"] != "password_reset"
            or not isinstance(subject, str)
            or not subject.isascii()
            or not subject.isdigit()
        ):
            raise ValueError("Invalid reset token.")

        user_id = int(subject)

        if not 1 <= user_id <= 2147483647:
            raise ValueError("Invalid user ID.")
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise invalid_token from exc

    try:
        # Lock and reload the row so a used token cannot reset it again.
        user = db.scalar(
            select(User)
            .where(User.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        if (
            user is None
            or user.status != "active"
            or not token_version_matches(payload, user.password_hash)
        ):
            raise invalid_token

        if verify_password(new_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Choose a different new password.",
            )

        user.password_hash = hash_password(new_password)
        db.commit()
    except Exception:
        db.rollback()
        raise

logger = logging.getLogger(__name__)

_rate_lock = Lock()
_rate_buckets: dict[str, deque[float]] = {}
_RATE_WINDOW = 3600


def _check_limits(limits: list[tuple[str, int]]) -> None:
    now = monotonic()

    with _rate_lock:
        for key in list(_rate_buckets):
            bucket = _rate_buckets[key]

            while bucket and bucket[0] <= now - _RATE_WINDOW:
                bucket.popleft()

            if not bucket:
                del _rate_buckets[key]

        if len(_rate_buckets) + len(limits) > 10000:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please try again later.",
            )

        for key, maximum in limits:
            if len(_rate_buckets.get(key, ())) >= maximum:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": "3600"},
                )

        for key, _ in limits:
            _rate_buckets.setdefault(key, deque()).append(now)


def check_request_limits(email: str, client_ip: str) -> None:
    email_key = hashlib.sha256(
        email.casefold().encode("utf-8")
    ).hexdigest()

    _check_limits([
        ("email:" + email_key, 3),
        ("request-ip:" + client_ip, 10),
    ])


def check_reset_limits(client_ip: str) -> None:
    _check_limits([("reset-ip:" + client_ip, 30)])


def send_reset_email(email: str) -> None:
    try:
        with SessionLocal() as db:
            user = db.scalar(
                select(User).where(
                    User.email == email,
                    User.status == "active",
                )
            )

            if user is None:
                return

            token = create_reset_token(user)
            recipient = user.email

        # A URL fragment keeps the token out of normal server request logs.
        link = RESET_PAGE_URL + "#token=" + quote(token, safe="")

        send_email(
            recipient,
            "VetDental: reset your password",
            (
                "We received a request to reset your VetDental password.\n\n"
                f"Open this link:\n{link}\n\n"
                f"This link expires in {RESET_EXPIRE_MINUTES} minutes.\n"
                "If you did not request this, you can ignore this email."
            ),
        )
    except Exception as exc:
        # Do not log credentials, reset tokens, or SMTP error contents.
        logger.error(
            "Password-reset email failed (%s).",
            type(exc).__name__,
        )