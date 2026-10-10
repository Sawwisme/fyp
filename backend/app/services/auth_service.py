from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PetOwner, User
from app.schemas.auth import LoginRequest, OwnerRegister

import bcrypt
import jwt

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    JWT_SECRET_KEY,
)


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")

    if not password_bytes or len(password_bytes) > 72:
        raise ValueError("Password must contain between 1 and 72 bytes.")

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(rounds=12),
    )
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")

    if not password_bytes or len(password_bytes) > 72:
        return False

    try:
        return bcrypt.checkpw(
            password_bytes,
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int) -> str:
    if isinstance(user_id, bool) or user_id <= 0:
        raise ValueError("A valid user ID is required.")

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid4()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        options={
            "require": [
                "sub",
                "iat",
                "nbf",
                "exp",
                "jti",
                "iss",
                "aud",
            ],
        },
    )

    subject = payload["sub"]

    if not isinstance(subject, str) or not subject.isascii():
        raise jwt.InvalidTokenError("Invalid token subject.")

    if not subject.isdigit() or int(subject) <= 0:
        raise jwt.InvalidTokenError("Invalid token subject.")

    return payload

def register_owner(db: Session, data: OwnerRegister) -> User:
    email = str(data.email)

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        full_name=data.full_name,
        email=email,
        password_hash=hash_password(data.password.get_secret_value()),
        phone_number=data.phone_number,
        role="pet_owner",
        status="active",
    )

    owner = PetOwner(default_address=data.default_address)
    user.pet_owner = owner

    try:
        db.add(user)
        db.flush()

        db.add(owner)
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        # MySQL error 1062 means a duplicate unique value.
        error_code = getattr(exc.orig, "args", (None,))[0]

        if error_code == 1062:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create the account.",
        ) from exc
    except Exception:
        db.rollback()
        raise

    db.refresh(user)
    return user

def authenticate_user(db: Session, data: LoginRequest) -> User:
    user = db.scalar(
        select(User).where(User.email == str(data.email))
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    password_valid = verify_password(
        data.password.get_secret_value(),
        user.password_hash,
    )

    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not active.",
        )

    return user