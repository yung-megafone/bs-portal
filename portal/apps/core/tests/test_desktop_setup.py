from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class DesktopInitialSetupTests(TestCase):
    @override_settings(DESKTOP_MODE=False)
    def test_setup_route_is_hidden_outside_desktop_build(self):
        response = self.client.get(reverse("desktop_setup"))
        self.assertEqual(response.status_code, 404)

    @override_settings(DESKTOP_MODE=True)
    def test_first_user_can_be_created_as_superuser(self):
        response = self.client.post(
            reverse("desktop_setup"),
            {
                "username": "oma",
                "display_name": "oma",
                "email": "",
                "password1": "A-long-local-admin-password-2026!",
                "password2": "A-long-local-admin-password-2026!",
            },
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertRedirects(response, reverse("dashboard"))
        user = get_user_model().objects.get(username="oma")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    @override_settings(DESKTOP_MODE=True)
    def test_setup_disables_after_any_user_exists(self):
        get_user_model().objects.create_user(username="existing", password="password-123")
        response = self.client.get(reverse("desktop_setup"), REMOTE_ADDR="127.0.0.1")
        self.assertRedirects(response, reverse("login"))

    @override_settings(DESKTOP_MODE=True)
    def test_setup_rejects_non_loopback_client(self):
        response = self.client.get(reverse("desktop_setup"), REMOTE_ADDR="10.0.0.10")
        self.assertEqual(response.status_code, 403)
