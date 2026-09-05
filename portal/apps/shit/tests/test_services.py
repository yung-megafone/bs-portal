from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from apps.departments.models import Department
from apps.identity.models import User
from apps.shit.models import Ticket, TicketEvent
from apps.shit.services import create_ticket, update_ticket


class TicketServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="requester",
            password="test-password",
        )
        self.department = Department.objects.create(
            code="SHIT",
            name="Software Helpdesk and Internet Technology",
        )

    def _create_ticket(self, title="Test"):
        return create_ticket(
            actor=self.user,
            title=title,
            description="Test ticket",
            ticket_type=Ticket.Type.REQUEST,
            severity=Ticket.Severity.SEV5,
            assigned_department=self.department,
        )

    def test_create_ticket_allocates_hex_number_and_event(self):
        ticket = self._create_ticket()

        self.assertRegex(
            ticket.ticket_number,
            r"^SHIT-\d{2}-[0-9A-F]{6}$",
        )
        self.assertTrue(
            ticket.events.filter(
                event_type=TicketEvent.EventType.CREATED
            ).exists()
        )

    def test_ticket_numbers_are_unique(self):
        first = self._create_ticket("First")
        second = self._create_ticket("Second")

        self.assertNotEqual(first.ticket_number, second.ticket_number)

    @patch(
        "apps.shit.services._generate_ticket_number",
        side_effect=[
            "SHIT-26-A4F29C",
            "SHIT-26-A4F29C",
            "SHIT-26-7C31AA",
        ],
    )
    def test_collision_retries_with_new_suffix(self, mocked_generator):
        first = self._create_ticket("First")
        second = self._create_ticket("Second")

        self.assertEqual(first.ticket_number, "SHIT-26-A4F29C")
        self.assertEqual(second.ticket_number, "SHIT-26-7C31AA")
        self.assertEqual(mocked_generator.call_count, 3)

    def test_status_change_is_audited(self):
        ticket = self._create_ticket()

        update_ticket(
            ticket=ticket,
            actor=self.user,
            status=Ticket.Status.IN_PROGRESS,
            severity=ticket.severity,
            assigned_department=self.department,
            assigned_user=None,
            related_document="",
        )

        self.assertTrue(
            ticket.events.filter(
                event_type=TicketEvent.EventType.STATUS_CHANGED
            ).exists()
        )
