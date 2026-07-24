from django.test import TestCase
from django.urls import reverse

from apps.departments.models import Department
from apps.identity.models import User


class DepartmentListTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="test-password-123")
        Department.objects.create(code="SR69", name="SubRosa69")

    def test_requires_authentication(self):
        response = self.client.get(reverse("departments:list"))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_can_view_departments(self):
        self.client.login(username="tester", password="test-password-123")
        response = self.client.get(reverse("departments:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SubRosa69")
