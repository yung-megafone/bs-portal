from django.test import TestCase
from django.urls import reverse

from apps.core.browser_preferences import cookie_name
from apps.departments.models import Department, DepartmentMembership
from apps.identity.models import User
from apps.shit.models import Ticket, TicketEvent
from apps.shit.services import create_ticket


class TicketBoardTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(
            username="requester",
            password="test-password",
        )
        self.agent = User.objects.create_user(
            username="agent",
            password="test-password",
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            password="test-password",
        )
        self.department = Department.objects.create(
            code="SHIT",
            name="Software Helpdesk and Internet Technology",
        )
        DepartmentMembership.objects.create(
            user=self.agent,
            department=self.department,
            is_active=True,
        )

    def _ticket(self, title):
        return create_ticket(
            actor=self.requester,
            title=title,
            description="Board test ticket",
            ticket_type=Ticket.Type.REQUEST,
            severity=Ticket.Severity.SEV3,
            assigned_department=self.department,
        )

    def test_board_is_default_view_without_saved_preference(self):
        ticket = self._ticket("Default board")
        self.client.force_login(self.agent)

        response = self.client.get(reverse("shit:list"), {"scope": "department"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["view_mode"], "board")
        self.assertContains(response, 'data-shit-board')
        self.assertContains(response, ticket.ticket_number)

    def test_explicit_list_view_is_remembered_by_browser_cookie(self):
        self._ticket("Remember list")
        self.client.force_login(self.agent)

        first = self.client.get(
            reverse("shit:list"),
            {"view": "list", "scope": "department"},
        )

        self.assertEqual(first.context["view_mode"], "list")
        self.assertEqual(
            first.cookies[cookie_name("shit-view")].value,
            "list",
        )

        second = self.client.get(reverse("shit:list"), {"scope": "department"})
        self.assertEqual(second.context["view_mode"], "list")
        self.assertNotContains(second, 'data-shit-board')

    def test_invalid_saved_view_falls_back_to_board(self):
        self._ticket("Invalid preference")
        self.client.force_login(self.agent)
        self.client.cookies[cookie_name("shit-view")] = "surprise"

        response = self.client.get(reverse("shit:list"), {"scope": "department"})

        self.assertEqual(response.context["view_mode"], "board")

    def test_ticket_detail_exposes_saved_density_preference(self):
        ticket = self._ticket("Compact detail")
        self.client.force_login(self.agent)
        self.client.cookies[cookie_name("shit-detail-density")] = "compact"

        response = self.client.get(
            reverse("shit:detail", args=[ticket.ticket_number])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["detail_density_preference"], "compact")
        self.assertContains(response, 'data-density="compact"')
        self.assertContains(response, 'data-saved-density="compact"')

    def test_board_renders_existing_ticket_records(self):
        ticket = self._ticket("Visible on board")
        self.client.force_login(self.agent)

        response = self.client.get(
            reverse("shit:list"),
            {"view": "board", "scope": "department"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ticket.ticket_number)
        self.assertContains(response, "Visible on board")

    def test_board_status_change_uses_normal_status_audit(self):
        ticket = self._ticket("Move status")
        self.client.force_login(self.agent)

        response = self.client.post(
            reverse("shit:board_move", args=[ticket.ticket_number]),
            {
                "status": Ticket.Status.IN_PROGRESS,
                "scope": "department",
            },
        )

        self.assertEqual(response.status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.IN_PROGRESS)
        self.assertTrue(
            ticket.events.filter(
                event_type=TicketEvent.EventType.STATUS_CHANGED
            ).exists()
        )

    def test_vertical_reorder_does_not_change_severity(self):
        first = self._ticket("First")
        second = self._ticket("Second")
        Ticket.objects.filter(pk=first.pk).update(queue_position=10)
        Ticket.objects.filter(pk=second.pk).update(queue_position=20)
        self.client.force_login(self.agent)

        response = self.client.post(
            reverse("shit:board_move", args=[second.ticket_number]),
            {
                "status": second.status,
                "direction": "up",
                "scope": "department",
            },
        )

        self.assertEqual(response.status_code, 302)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertLess(second.queue_position, first.queue_position)
        self.assertEqual(second.severity, Ticket.Severity.SEV3)
        self.assertTrue(
            second.events.filter(
                event_type=TicketEvent.EventType.QUEUE_REORDERED
            ).exists()
        )

    def test_requester_visibility_does_not_grant_board_manage_permission(self):
        ticket = self._ticket("Requester cannot manage queue")
        self.client.force_login(self.requester)

        response = self.client.post(
            reverse("shit:board_move", args=[ticket.ticket_number]),
            {"status": Ticket.Status.IN_PROGRESS},
        )

        self.assertEqual(response.status_code, 403)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.NEW)

    def test_unrelated_user_cannot_reach_ticket_through_board_endpoint(self):
        ticket = self._ticket("Outsider denied")
        self.client.force_login(self.outsider)

        response = self.client.post(
            reverse("shit:board_move", args=[ticket.ticket_number]),
            {"status": Ticket.Status.IN_PROGRESS},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.NEW)
