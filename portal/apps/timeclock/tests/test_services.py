from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.identity.models import User
from apps.timeclock.models import Punch, PunchCorrection, TimeclockEvent
from apps.timeclock.services import clock_in, clock_out, correct_punch, get_clock_state


class TimeclockServiceTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            username="employee",
            password="test-password-123",
        )
        self.admin = User.objects.create_user(
            username="administrator",
            password="test-password-123",
            is_staff=True,
        )

    def test_clock_in_and_out_use_server_records_and_audit_events(self):
        punch_in = clock_in(employee=self.employee, actor=self.employee)

        self.assertEqual(punch_in.punch_type, Punch.PunchType.IN)
        self.assertEqual(punch_in.source, Punch.Source.PORTAL)
        self.assertTrue(get_clock_state(self.employee).is_clocked_in)
        self.assertTrue(
            TimeclockEvent.objects.filter(
                punch=punch_in,
                event_type=TimeclockEvent.EventType.CLOCK_IN,
                employee=self.employee,
                actor=self.employee,
            ).exists()
        )

        punch_out = clock_out(employee=self.employee, actor=self.employee)
        self.assertEqual(punch_out.punch_type, Punch.PunchType.OUT)
        self.assertFalse(get_clock_state(self.employee).is_clocked_in)

    def test_invalid_duplicate_state_transitions_are_rejected(self):
        with self.assertRaises(ValidationError):
            clock_out(employee=self.employee, actor=self.employee)

        clock_in(employee=self.employee, actor=self.employee)

        with self.assertRaises(ValidationError):
            clock_in(employee=self.employee, actor=self.employee)

    def test_user_cannot_punch_for_another_user(self):
        with self.assertRaises(PermissionDenied):
            clock_in(employee=self.employee, actor=self.admin)

    def test_admin_correction_preserves_original_punch(self):
        original = clock_in(employee=self.employee, actor=self.employee)
        original_type = original.punch_type
        original_time = original.occurred_at
        corrected_time = original_time - timedelta(minutes=5)

        correction = correct_punch(
            punch=original,
            actor=self.admin,
            corrected_punch_type=Punch.PunchType.IN,
            corrected_occurred_at=corrected_time,
            reason="Verified missed five minutes at shift start.",
        )

        original.refresh_from_db()

        self.assertEqual(original.punch_type, original_type)
        self.assertEqual(original.occurred_at, original_time)
        self.assertEqual(PunchCorrection.objects.count(), 1)
        self.assertEqual(correction.corrected_by, self.admin)
        self.assertEqual(original.effective_occurred_at, corrected_time)
        self.assertTrue(
            TimeclockEvent.objects.filter(
                punch=original,
                event_type=TimeclockEvent.EventType.CORRECTION,
                actor=self.admin,
                employee=self.employee,
            ).exists()
        )

    def test_nonstaff_cannot_correct_punch(self):
        original = clock_in(employee=self.employee, actor=self.employee)

        with self.assertRaises(PermissionDenied):
            correct_punch(
                punch=original,
                actor=self.employee,
                corrected_punch_type=Punch.PunchType.IN,
                corrected_occurred_at=timezone.now(),
                reason="Should fail.",
            )
