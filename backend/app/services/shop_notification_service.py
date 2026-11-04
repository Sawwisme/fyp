from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ClinicAdministrator,
    Notification,
    PetOwner,
    User,
)


def notify_shop_event(
    db: Session,
    order,
    event_key: str,
    title: str,
    message: str,
    *,
    include_owner: bool = True,
    include_admins: bool = False,
):
    """
    Add notifications within the calling transaction.
    The caller must already hold the clinic/order locks.
    """
    recipients = set()

    if include_owner:
        owner_user_id = db.scalar(
            select(PetOwner.user_id)
            .join(
                User,
                User.user_id == PetOwner.user_id,
            )
            .where(
                PetOwner.pet_owner_id == order.pet_owner_id,
                User.role == "pet_owner",
                User.status == "active",
            )
        )

        if owner_user_id is not None:
            recipients.add(owner_user_id)

    if include_admins:
        recipients.update(
            db.scalars(
                select(ClinicAdministrator.user_id)
                .join(
                    User,
                    User.user_id
                    == ClinicAdministrator.user_id,
                )
                .where(
                    ClinicAdministrator.clinic_id
                    == order.clinic_id,
                    ClinicAdministrator.membership_status
                    == "approved",
                    User.role == "clinic_administrator",
                    User.status == "active",
                )
            ).all()
        )

    if not recipients:
        return

    existing_users = set(
        db.scalars(
            select(Notification.user_id)
            .where(
                Notification.user_id.in_(recipients),
                Notification.event_key == event_key,
            )
        ).all()
    )

    # SessionLocal has autoflush disabled, so also check
    # notifications added earlier in this transaction.
    existing_users.update(
        item.user_id
        for item in db.new
        if isinstance(item, Notification)
        and item.event_key == event_key
    )

    for user_id in sorted(recipients - existing_users):
        db.add(
            Notification(
                user_id=user_id,
                event_key=event_key,
                notification_type="shop_update",
                title=title,
                message=message,
                resource_type="shop_order",
                resource_id=order.order_id,
            )
        )

    # No commit here. Notifications save with the order action.