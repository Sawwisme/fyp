import unittest
from datetime import datetime
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Notification
from app.services import notification_service as service


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Notification.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

        self.owner = SimpleNamespace(user_id=1)
        self.other_owner = SimpleNamespace(user_id=2)

    def add_notification(
        self, user_id=1, event_key="assessment:7:completed",
        resource_type="dental_assessment", resource_id=7,
        created_at=None,
    ):
        record = Notification(
            user_id=user_id,
            event_key=event_key,
            notification_type="dental_assessment_completed",
            title="Assessment ready",
            message="Open your assessment.",
            resource_type=resource_type,
            resource_id=resource_id,
            created_at=created_at or datetime(2026, 11, 25),
        )
        self.db.add(record)
        self.db.commit()
        return record

    def test_first_poll_does_not_replay_old_notifications(self):
        owned = self.add_notification()
        self.add_notification(user_id=2)

        result = service.get_notification_updates(
            self.db, self.owner
        )

        self.assertEqual(result["items"], [])
        self.assertEqual(result["cursor"], owned.notification_id)

    def test_updates_exclude_other_accounts(self):
        owned = self.add_notification()
        self.add_notification(user_id=2)

        result = service.get_notification_updates(
            self.db, self.owner, after_id=0
        )

        self.assertEqual(
            [item.notification_id for item in result["items"]],
            [owned.notification_id],
        )
        self.assertEqual(result["cursor"], owned.notification_id)

    def test_advanced_cursor_does_not_replay_notification(self):
        record = self.add_notification()

        result = service.get_notification_updates(
            self.db, self.owner,
            after_id=record.notification_id,
        )

        self.assertEqual(result["items"], [])
        self.assertEqual(result["cursor"], record.notification_id)

    def test_backdated_new_notification_is_not_missed(self):
        first = self.add_notification()
        second = self.add_notification(
            event_key="assessment:8:completed",
            resource_id=8,
            created_at=datetime(2020, 1, 1),
        )

        result = service.get_notification_updates(
            self.db, self.owner,
            after_id=first.notification_id,
        )

        self.assertEqual(
            [item.notification_id for item in result["items"]],
            [second.notification_id],
        )

    def test_detail_returns_exact_resource(self):
        record = self.add_notification(
            resource_type="appointment",
            resource_id=42,
        )

        result = service.get_notification_by_id(
            self.db, self.owner, record.notification_id
        )

        self.assertEqual(result.resource_type, "appointment")
        self.assertEqual(result.resource_id, 42)

    def test_other_account_cannot_open_notification(self):
        record = self.add_notification()

        with self.assertRaises(HTTPException) as caught:
            service.get_notification_by_id(
                self.db, self.other_owner,
                record.notification_id,
            )

        self.assertEqual(caught.exception.status_code, 404)

    def test_other_account_cannot_mark_notification_read(self):
        record = self.add_notification()

        with self.assertRaises(HTTPException) as caught:
            service.mark_as_read(
                self.db, self.other_owner,
                record.notification_id,
            )

        self.assertEqual(caught.exception.status_code, 404)
        self.db.refresh(record)
        self.assertIsNone(record.read_at)

    def test_repeated_read_preserves_first_timestamp(self):
        record = self.add_notification()

        first = service.mark_as_read(
            self.db, self.owner, record.notification_id
        )
        second = service.mark_as_read(
            self.db, self.owner, record.notification_id
        )

        self.assertIsNotNone(first.read_at)
        self.assertEqual(first.read_at, second.read_at)

    def test_duplicate_event_is_rejected_for_same_account(self):
        self.add_notification()

        with self.assertRaises(IntegrityError):
            self.add_notification()

        self.db.rollback()

    def test_same_event_can_notify_different_accounts(self):
        self.add_notification(user_id=1)
        self.add_notification(user_id=2)

        self.assertEqual(
            service.get_my_unread_count(self.db, self.owner),
            {"unread_count": 1},
        )
        self.assertEqual(
            service.get_my_unread_count(self.db, self.other_owner),
            {"unread_count": 1},
        )


if __name__ == "__main__":
    unittest.main()