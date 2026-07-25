import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Punch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("punch_type", models.CharField(choices=[("IN", "Clock in"), ("OUT", "Clock out")], max_length=8)),
                ("occurred_at", models.DateTimeField()),
                ("source", models.CharField(choices=[("PORTAL", "B.S. Portal"), ("IMPORT", "Imported"), ("API", "API"), ("TERMINAL", "Terminal")], default="PORTAL", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timeclock_punches", to=settings.AUTH_USER_MODEL)),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timeclock_punches_recorded", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["occurred_at", "created_at"]},
        ),
        migrations.CreateModel(
            name="PunchCorrection",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("corrected_punch_type", models.CharField(choices=[("IN", "Clock in"), ("OUT", "Clock out")], max_length=8)),
                ("corrected_occurred_at", models.DateTimeField()),
                ("reason", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("corrected_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timeclock_corrections", to=settings.AUTH_USER_MODEL)),
                ("punch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="corrections", to="timeclock.punch")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="TimeclockEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(choices=[("CLOCK_IN", "Clocked in"), ("CLOCK_OUT", "Clocked out"), ("CORRECTION", "Punch corrected")], max_length=24)),
                ("summary", models.CharField(max_length=240)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timeclock_events_as_actor", to=settings.AUTH_USER_MODEL)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timeclock_events_as_employee", to=settings.AUTH_USER_MODEL)),
                ("punch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="events", to="timeclock.punch")),
            ],
            options={"ordering": ["-occurred_at"]},
        ),
        migrations.AddIndex(
            model_name="punch",
            index=models.Index(fields=["employee", "occurred_at"], name="timeclock_pu_employe_6c764f_idx"),
        ),
        migrations.AddIndex(
            model_name="punch",
            index=models.Index(fields=["employee", "punch_type"], name="timeclock_pu_employe_0ca188_idx"),
        ),
        migrations.AddIndex(
            model_name="punchcorrection",
            index=models.Index(fields=["punch", "created_at"], name="timeclock_pu_punch_i_328cb9_idx"),
        ),
        migrations.AddIndex(
            model_name="punchcorrection",
            index=models.Index(fields=["corrected_by", "created_at"], name="timeclock_pu_correct_1dc4d6_idx"),
        ),
        migrations.AddIndex(
            model_name="timeclockevent",
            index=models.Index(fields=["employee", "occurred_at"], name="timeclock_ti_employe_b43d75_idx"),
        ),
        migrations.AddIndex(
            model_name="timeclockevent",
            index=models.Index(fields=["actor", "occurred_at"], name="timeclock_ti_actor_i_7af06a_idx"),
        ),
    ]
