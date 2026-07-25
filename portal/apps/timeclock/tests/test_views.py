from django.test import TestCase
from django.urls import reverse

from apps.identity.models import User
from apps.timeclock.models import Punch


class TimeclockViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="worker",
            password="test-password-123",
        )

    def test_timeclock_requires_authentication(self):
        response = self.client.get(reverse("timeclock:home"))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_can_clock_in_and_out(self):
        self.client.login(username="worker", password="test-password-123")

        response = self.client.post(
            reverse("timeclock:punch"),
            {"action": "in"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Punch.objects.count(), 1)

        response = self.client.post(
            reverse("timeclock:punch"),
            {"action": "out"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Punch.objects.count(), 2)

    def test_timeclock_page_does_not_request_surveillance_inputs(self):
        self.client.login(username="worker", password="test-password-123")
        response = self.client.get(reverse("timeclock:home"))
        content = response.content.decode().lower()

        # The page may explicitly state that surveillance data is NOT collected.
        # Test for mechanisms that would actually request/capture such data instead.
        self.assertNotIn("navigator.geolocation", content)
        self.assertNotIn("getusermedia", content)
        self.assertNotIn('type="file"', content)
        self.assertNotIn("webauthn", content)

        self.assertContains(
            response,
            "No location, biometric, device fingerprint, or surveillance data is collected by this module.",
        )