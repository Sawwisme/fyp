from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.orm import Session

from fastapi import HTTPException
from app.schemas.auth import StaffLoginRequest

from app.dependencies import get_current_user
from app.models import User

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import get_db

from pathlib import Path as FilePath

from fastapi.responses import FileResponse

from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    OwnerRegister,
    PasswordChangeRequest,
    TokenResponse,
    ForgotPasswordRequest, 
    ResetPasswordRequest,
)

from app.schemas.user import UserResponse

from app.services.auth_service import (
    authenticate_user,
    change_password,
    create_access_token,
    register_owner,
)

from app.services.auth_service import (
    authenticate_user,
    change_password,
    create_access_token,
    register_owner,
)

from app.services import password_reset_service

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "Email already registered"},
    },
)
def register(
    data: OwnerRegister,
    db: Session = Depends(get_db),
):
    return register_owner(db, data)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"description": "Incorrect email or password"},
        403: {"description": "Account is not active"},
    },
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, data)

    return TokenResponse(
        access_token=create_access_token(
            user.user_id,
            user.password_hash,
        ),
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )

@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"description": "Invalid or missing token"},
        403: {"description": "Account is not active"},
    },
)
def get_my_account(
    current_user: User = Depends(get_current_user),
):
    return current_user

@router.post(
    "/change-password",
    response_model=MessageResponse,
    responses={
        400: {"description": "Incorrect current password or unchanged password"},
        401: {"description": "Invalid or missing token"},
        403: {"description": "Account is not active"},
    },
)
def change_my_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change_password(db, current_user, data)

    return MessageResponse(
        message="Password changed. Please log in again.",
    )

@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        429: {"description": "Too many reset requests"},
    },
)
def request_password_reset(
    data: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    email = str(data.email)
    client_ip = request.client.host if request.client else "unknown"

    password_reset_service.check_request_limits(email, client_ip)

    background_tasks.add_task(
        password_reset_service.send_reset_email,
        email,
    )

    return MessageResponse(
        message=(
            "If an active account exists for this email, "
            "a password-reset link will be sent."
        ),
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    responses={
        400: {"description": "Invalid, expired, or already used reset link"},
        429: {"description": "Too many reset attempts"},
    },
)
def complete_password_reset(
    data: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    password_reset_service.check_reset_limits(client_ip)

    password_reset_service.reset_password(
        db,
        data.token.get_secret_value(),
        data.new_password.get_secret_value(),
    )

    return MessageResponse(
        message="Password reset successfully. Log in with your new password.",
    )

@router.get(
    "/reset-password",
    response_class=FileResponse,
    include_in_schema=False,
)
def show_password_reset_page():
    page = (
        FilePath(__file__).resolve().parent.parent
        / "pages"
        / "password_reset.html"
    )

    return FileResponse(
        path=page,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": (
                "default-src 'none'; "
                "style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; "
                "connect-src 'self'; "
                "base-uri 'none'; "
                "frame-ancestors 'none'; "
                "form-action 'self'"
            ),
        },
    )

@router.post(
    "/staff-login",
    response_model=TokenResponse,
)
def staff_login(
    data: StaffLoginRequest,
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, data)

    if user.role != data.role:
        raise HTTPException(
            status_code=403,
            detail=(
                "This account does not match the selected staff role. "
                "Select the correct login tab."
            ),
        )

    return TokenResponse(
        access_token=create_access_token(
            user.user_id,
            user.password_hash,
        ),
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )