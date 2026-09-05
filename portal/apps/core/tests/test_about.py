from django.test import TestCase
from django.urls import reverse

from apps.core.version import __version__


class PublicInformationViewsTests(TestCase):
    def test_about_is_public_and_displays_release_metadata(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "About B.S. Portal")
        self.assertContains(response, __version__)
        self.assertContains(response, "MIT")

    def test_privacy_policy_is_public(self):
        response = self.client.get(reverse("privacy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Privacy first")
        self.assertContains(response, "No advertising or ad-tech tracking")

    def test_security_policy_is_public(self):
        response = self.client.get(reverse("security"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Security posture")
        self.assertContains(response, "alpha software")

    def test_license_is_public(self):
        response = self.client.get(reverse("license"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MIT License")
        self.assertContains(response, "B.S. Supply Co.")
