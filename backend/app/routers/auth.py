from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.models import User

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import get_db
from app.schemas.auth import LoginRequest, OwnerRegister, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    register_owner,
)


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
        access_token=create_access_token(user.user_id),
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