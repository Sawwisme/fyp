import unittest
from types import SimpleNamespace as Obj
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from pydantic import ValidationError
from app.schemas.staff import VeterinarianStatusUpdate
from app.services.staff_service import update_veterinarian_status


class StaffAccountStatusTests(unittest.TestCase):
    def run_change(self, existing="active", target="inactive", blockers=(0, 0, 0), vet_clinic=True, approved="approved"):
        self.db = MagicMock()
        self.user = Obj(user_id=8, status=existing)
        vet = Obj(veterinarian_id=7, user_id=8, approval_status=approved)
        self.db.scalar.side_effect = [Obj(clinic_id=2), vet if vet_clinic else None, self.user, *blockers]
        data = VeterinarianStatusUpdate(status=target, expected_status=existing)
        with patch('app.services.staff_service.get_admin_record', return_value=Obj(clinic_id=2)):
            return update_veterinarian_status(self.db, Obj(user_id=1), 7, data)

    def test_deactivate_preserves_records_and_changes_only_status(self):
        result=self.run_change()
        self.assertEqual(result['status'], 'inactive')
        self.assertEqual(self.user.status, 'inactive')
        self.db.commit.assert_called_once()
        self.db.delete.assert_not_called()
        # Both ownership and role scoping are present in the executed queries.
        self.assertIn('clinic_id', str(self.db.scalar.call_args_list[1].args[0]))
        self.assertIn('users.role', str(self.db.scalar.call_args_list[2].args[0]))

    def test_reactivate_approved_vet(self):
        self.assertEqual(self.run_change(existing='inactive', target='active')['status'], 'active')
        self.db.commit.assert_called_once()

    def test_other_clinic_is_not_found(self):
        with self.assertRaises(HTTPException) as error:
            self.run_change(vet_clinic=False)
        self.assertEqual(error.exception.status_code, 404)
        self.db.commit.assert_not_called()

    def test_appointments_block_deactivation(self):
        with self.assertRaises(HTTPException) as error:
            self.run_change(blockers=(1, 0, 0))
        self.assertEqual(error.exception.status_code,409)
        self.assertIn('appointment',error.exception.detail)
        self.assertEqual(self.user.status,'active')
        self.db.commit.assert_not_called()

    def test_open_followups_block_deactivation(self):
        with self.assertRaises(HTTPException) as error:
            self.run_change(blockers=(0, 1, 0))
        self.assertIn('follow-up',error.exception.detail)
        self.db.commit.assert_not_called()

    def test_unfinished_consultation_blocks_deactivation(self):
        with self.assertRaises(HTTPException) as error:
            self.run_change(blockers=(0, 0, 1))
        self.assertIn('consultation',error.exception.detail)
        self.db.commit.assert_not_called()

    def test_unapproved_vet_cannot_be_reactivated(self):
        with self.assertRaises(HTTPException) as error:
            self.run_change(existing='inactive',target='active',approved='pending')
        self.assertEqual(error.exception.status_code,409)

    def test_repeat_request_does_not_commit(self):
        self.run_change(existing='inactive',target='inactive')
        self.db.commit.assert_not_called()

    def test_invalid_status_rejected(self):
        with self.assertRaises(ValidationError):
            VeterinarianStatusUpdate(status='deleted',expected_status='active')
