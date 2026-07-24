import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=20, unique=True)),
                ("name", models.CharField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="DepartmentMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role", models.CharField(choices=[("MEMBER", "Member"), ("MANAGER", "Manager"), ("ADMIN", "Department administrator")], default="MEMBER", max_length=20)),
                ("started_at", models.DateField(blank=True, null=True)),
                ("ended_at", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("department", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="departments.department")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="department_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["department__code", "user__username"]},
        ),
        migrations.AddConstraint(
            model_name="department",
            constraint=models.CheckConstraint(condition=models.Q(code__regex=r"^[A-Z0-9][A-Z0-9_-]*$"), name="department_code_format"),
        ),
        migrations.AddConstraint(
            model_name="departmentmembership",
            constraint=models.UniqueConstraint(condition=models.Q(is_active=True), fields=("user", "department"), name="one_active_membership_per_user_department"),
        ),
        migrations.AddConstraint(
            model_name="departmentmembership",
            constraint=models.CheckConstraint(condition=models.Q(ended_at__isnull=True) | models.Q(started_at__isnull=True) | models.Q(ended_at__gte=models.F("started_at")), name="membership_end_not_before_start"),
        ),
    ]
