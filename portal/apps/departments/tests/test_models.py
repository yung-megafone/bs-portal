from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.departments.models import Department, DepartmentMembership
from apps.identity.models import User


class DepartmentTests(TestCase):
    def test_department_code_is_unique(self):
        Department.objects.create(code="SR69", name="SubRosa69")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Department.objects.create(code="SR69", name="Duplicate")

    def test_active_membership_is_unique_per_user_and_department(self):
        user = User.objects.create_user(username="tester")
        department = Department.objects.create(code="OPS", name="Operations")
        DepartmentMembership.objects.create(user=user, department=department)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DepartmentMembership.objects.create(user=user, department=department)

    def test_ended_membership_allows_new_active_membership(self):
        user = User.objects.create_user(username="tester")
        department = Department.objects.create(code="OPS", name="Operations")
        DepartmentMembership.objects.create(
            user=user,
            department=department,
            started_at=date(2026, 1, 1),
            ended_at=date(2026, 6, 1),
            is_active=False,
        )
        DepartmentMembership.objects.create(user=user, department=department, is_active=True)
        self.assertEqual(DepartmentMembership.objects.filter(user=user, department=department).count(), 2)
