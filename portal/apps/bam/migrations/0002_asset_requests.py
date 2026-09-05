# Generated for B.S. Portal Chunk 3 — BAM asset request / reservation queue.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bam", "0001_initial"),
        ("shit", "0004_ticket_asset_links"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assetevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("REGISTERED", "Registered"),
                    ("UPDATED", "Updated"),
                    ("STATUS_CHANGED", "Status changed"),
                    ("CUSTODY_ASSIGNED", "Custody assigned"),
                    ("CUSTODY_RETURNED", "Custody returned"),
                    ("EVIDENCE_ADDED", "Evidence added"),
                    ("RESERVATION_ALLOCATED", "Reservation allocated"),
                    ("RESERVATION_RELEASED", "Reservation released"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="AssetRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("request_number", models.CharField(editable=False, max_length=32, unique=True)),
                ("purpose", models.CharField(max_length=200)),
                ("justification", models.TextField(blank=True)),
                ("priority", models.CharField(choices=[("NORMAL", "Normal"), ("TIME_SENSITIVE", "Time-sensitive"), ("CRITICAL_DEPENDENCY", "Critical dependency")], default="NORMAL", max_length=24)),
                ("status", models.CharField(choices=[("SUBMITTED", "Submitted"), ("QUEUED", "Queued"), ("PARTIALLY_RESERVED", "Partially reserved"), ("RESERVED", "Reserved"), ("DENIED", "Denied"), ("CANCELLED", "Cancelled"), ("COMPLETED", "Completed")], default="SUBMITTED", max_length=24)),
                ("requested_start", models.DateField()),
                ("requested_end", models.DateField()),
                ("desired_completion_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("related_ticket", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asset_requests", to="shit.ticket")),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bam_asset_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["requester", "status"], name="bam_req_requester_status_idx"),
                    models.Index(fields=["status", "requested_start"], name="bam_req_status_start_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(requested_end__gte=models.F("requested_start")), name="bam_request_end_not_before_start"),
                    models.CheckConstraint(condition=models.Q(desired_completion_date__isnull=True) | models.Q(desired_completion_date__gte=models.F("requested_start")), name="bam_request_due_not_before_start"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AssetRequestItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("preference_mode", models.CharField(choices=[("ANY", "Any suitable asset"), ("PREFER", "Prefer this asset; allow equivalent"), ("REQUIRE", "Require this exact asset")], default="ANY", max_length=12)),
                ("status", models.CharField(choices=[("PENDING", "Pending review"), ("WAITLISTED", "Waitlisted"), ("ALLOCATED", "Reserved"), ("RELEASED", "Released"), ("DENIED", "Denied"), ("CANCELLED", "Cancelled")], default="PENDING", max_length=16)),
                ("note", models.CharField(blank=True, max_length=240)),
                ("allocated_at", models.DateTimeField(blank=True, null=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("allocated_asset", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="allocated_request_items", to="bam.asset")),
                ("allocated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="bam_allocations_made", to=settings.AUTH_USER_MODEL)),
                ("asset_type", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="request_items", to="bam.assettype")),
                ("department", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="asset_request_items", to="departments.department")),
                ("preferred_asset", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="preferred_request_items", to="bam.asset")),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="bam.assetrequest")),
            ],
            options={
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(fields=["department", "asset_type", "status"], name="bam_reqitem_pool_status_idx"),
                    models.Index(fields=["preferred_asset", "status"], name="bam_reqitem_pref_status_idx"),
                    models.Index(fields=["allocated_asset", "status"], name="bam_reqitem_alloc_status_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(preference_mode="ANY") | models.Q(preferred_asset__isnull=False), name="bam_reqitem_preferred_when_specific"),
                    models.CheckConstraint(condition=~models.Q(status="ALLOCATED") | models.Q(allocated_asset__isnull=False), name="bam_reqitem_allocated_has_asset"),
                    models.CheckConstraint(condition=models.Q(released_at__isnull=True) | models.Q(allocated_at__isnull=True) | models.Q(released_at__gte=models.F("allocated_at")), name="bam_reqitem_release_after_alloc"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AssetRequestEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(choices=[("CREATED", "Created"), ("ITEM_ADDED", "Requirement added"), ("WAITLISTED", "Waitlisted"), ("ALLOCATED", "Reserved"), ("RELEASED", "Reservation released"), ("DENIED", "Denied"), ("CANCELLED", "Cancelled"), ("COMPLETED", "Completed")], max_length=24)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                ("summary", models.CharField(max_length=240)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bam_asset_request_events", to=settings.AUTH_USER_MODEL)),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="events", to="bam.assetrequest")),
            ],
            options={"ordering": ["-occurred_at"]},
        ),
    ]
