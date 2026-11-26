from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.notifications import NotificationResponse
from app.services import notification_service


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


@router.get(
    "",
    response_model=list[NotificationResponse],
)
def list_my_notifications(
    unread_only: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_service.list_my_notifications(
        db,
        current_user,
        unread_only,
        offset,
        limit,
    )


@router.get(
    "/unread-count",
    response_model=dict[str, int],
)
def get_my_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_service.get_my_unread_count(
        db,
        current_user,
    )

@router.get("/updates")
def get_notification_updates(
    after_id: int | None = Query(default=None, ge=0, le=2147483647),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_service.get_notification_updates(
        db, current_user, after_id
    )

@router.post("/read-all")
def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_service.mark_all_as_read(
        db,
        current_user,
    )

@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
def mark_notification_as_read(
    notification_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_service.mark_as_read(
        db,
        current_user,
        notification_id,
    )


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
)
def get_my_notification(
    notification_id: int = Path(ge=1, le=2147483647),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_service.get_notification_by_id(
        db,
        current_user,
        notification_id,
    )
