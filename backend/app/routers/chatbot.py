from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import User
from app.schemas.chatbot import (
    ConversationCreate,
    MessageCreate,
)
from app.services import chatbot_service


router = APIRouter(
    prefix="/chatbot",
    tags=["Chatbot"],
)


@router.post("/conversations", status_code=201)
def create_conversation(
    data: ConversationCreate,
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return chatbot_service.create_conversation(
        db,
        current_user,
        data,
    )


@router.get("/conversations")
def list_conversations(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return chatbot_service.list_conversations(
        db,
        current_user,
        offset,
        limit,
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return chatbot_service.get_conversation(
        db,
        current_user,
        conversation_id,
    )


@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: int = Path(ge=1, le=2147483647),
    before_message_id: int | None = Query(
        default=None,
        ge=1,
        le=2147483647,
    ),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return chatbot_service.list_messages(
        db,
        current_user,
        conversation_id,
        before_message_id,
        limit,
    )


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    data: MessageCreate,
    conversation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return chatbot_service.send_message(
        db,
        current_user,
        conversation_id,
        data,
    )


@router.post("/conversations/{conversation_id}/close")
def close_conversation(
    conversation_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(require_roles("pet_owner")),
    db: Session = Depends(get_db),
):
    return chatbot_service.close_conversation(
        db,
        current_user,
        conversation_id,
    )