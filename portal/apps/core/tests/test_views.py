from django.test import TestCase
from django.urls import reverse

from apps.identity.models import User


class HealthViewTests(TestCase):
    def test_health_is_public_and_ok(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="test-password-123")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_authenticated_user_can_view_dashboard(self):
        self.client.login(username="tester", password="test-password-123")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "B.S. Portal")
