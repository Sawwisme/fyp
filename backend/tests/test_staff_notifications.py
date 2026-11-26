import unittest
from types import SimpleNamespace as Obj
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
from app.models import Notification
from app.services import staff_notification_service as service


class StaffNotificationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Notification.__table__.create(self.engine)
        with self.engine.begin() as conn:
            for sql in [
                "CREATE TABLE users (user_id INTEGER PRIMARY KEY, role TEXT, status TEXT)",
                "CREATE TABLE veterinarians (veterinarian_id INTEGER PRIMARY KEY, user_id INTEGER, approval_status TEXT)",
                "CREATE TABLE clinic_administrators (user_id INTEGER, clinic_id INTEGER, membership_status TEXT)",
                "INSERT INTO users VALUES (1, 'veterinarian', 'active'), (2, 'clinic_administrator', 'active'), (3, 'clinic_administrator', 'active'), (4, 'clinic_administrator', 'inactive')",
                "INSERT INTO veterinarians VALUES (7,1,'approved')",
                "INSERT INTO clinic_administrators VALUES (2,10,'approved'), (3,11,'approved'), (4,10,'approved')",
            ]:
                conn.execute(text(sql))
        self.db = Session(self.engine, autoflush=False)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

    def booking(self, status="confirmed"):
        return Obj(status=status, pet_id=5, veterinarian_id=7,
                   appointment_id=12, appointment_date="2026-11-27", ai_analysis_id=9)

    def test_booking_targets_assigned_vet_and_mentions_scan(self):
        from unittest.mock import patch
        with patch.object(self.db, "get", return_value=Obj(pet_name="Kopi")):
            service.notify_booking_confirmed(self.db, self.booking())
        self.db.flush()
        row = self.db.scalar(select(Notification))
        self.assertEqual(row.user_id, 1)
        self.assertIn("AI assessment is attached", row.message)
        self.assertEqual(row.resource_id, 12)

    def test_pending_payment_does_not_notify(self):
        service.notify_booking_confirmed(self.db, self.booking("pending_payment"))
        self.assertEqual(len(self.db.new), 0)

    def test_emergency_only_active_admin_at_matching_clinic(self):
        service.notify_emergency_requested(self.db, Obj(clinic_id=10, emergency_appointment_id=15))
        self.db.flush()
        self.assertEqual(list(self.db.scalars(select(Notification.user_id))), [2])

    def test_duplicate_pending_and_persisted_event_is_not_replayed(self):
        args=(self.db, 1, "unique-event", "Title", "Message", "staff_appointment", 12)
        service._add(*args)
        service._add(*args)
        self.assertEqual(len(self.db.new), 1)
        self.db.flush()
        service._add(*args)
        self.assertEqual(len(self.db.new), 0)

    def test_followup_targets_responsible_vet(self):
        from unittest.mock import patch
        with patch.object(self.db, "get", return_value=Obj(pet_name="Kopi")):
            service.notify_followup_submitted(self.db,
                Obj(pet_id=5, veterinarian_id=7, followup_care_id=20), Obj(submission_id=30))
        self.db.flush()
        row=self.db.scalar(select(Notification))
        self.assertEqual((row.user_id, row.resource_type, row.resource_id), (1, "staff_followup", 20))

    def test_notification_rolls_back_with_action(self):
        service._add(self.db, 1, "rollback", "Title", "Message", "staff_appointment", 12)
        self.db.flush()
        self.db.rollback()
        self.assertIsNone(self.db.scalar(select(Notification)))
