import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(
                condition=Q(code__regex=r"^[A-Z0-9][A-Z0-9_-]*$"),
                name="department_code_format",
            )
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class DepartmentMembership(models.Model):
    class Role(models.TextChoices):
        MEMBER = "MEMBER", "Member"
        MANAGER = "MANAGER", "Manager"
        ADMIN = "ADMIN", "Department administrator"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="department_memberships",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    started_at = models.DateField(null=True, blank=True)
    ended_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["department__code", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "department"],
                condition=Q(is_active=True),
                name="one_active_membership_per_user_department",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(started_at__isnull=True) | Q(ended_at__gte=models.F("started_at")),
                name="membership_end_not_before_start",
            ),
        ]

    def __str__(self):
        return f"{self.user} / {self.department.code} / {self.get_role_display()}"
