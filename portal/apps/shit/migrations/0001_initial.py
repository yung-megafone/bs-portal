import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("departments", "0002_membership_unique_mysql"),
        ("bam", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(name="TicketSequence", fields=[("year", models.PositiveSmallIntegerField(primary_key=True, serialize=False)), ("last_value", models.PositiveBigIntegerField(default=0))]),
        migrations.CreateModel(name="Ticket", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("ticket_number", models.CharField(editable=False, max_length=32, unique=True)),
            ("title", models.CharField(max_length=200)), ("description", models.TextField()),
            ("ticket_type", models.CharField(choices=[("INCIDENT","Incident"),("REQUEST","Service request"),("ACCESS","Access request"),("CHANGE","Change request"),("PROBLEM","Problem"),("PSOP","PSOP / documentation"),("FEEDBACK","Feedback / note"),("OTHER","Other")], default="REQUEST", max_length=24)),
            ("severity", models.CharField(choices=[("NONE","NONE"),("SEV5","SEV-5"),("SEV4","SEV-4"),("SEV3","SEV-3"),("SEV2","SEV-2"),("SEV1","SEV-1")], default="SEV5", max_length=8)),
            ("status", models.CharField(choices=[("NEW","New"),("ACKNOWLEDGED","Acknowledged"),("ASSIGNED","Assigned"),("IN_PROGRESS","In progress"),("WAITING_REQUESTER","Waiting on requester"),("WAITING_VENDOR","Waiting on vendor"),("RESOLVED","Resolved"),("CLOSED","Closed"),("CANCELLED","Cancelled")], default="NEW", max_length=24)),
            ("related_document", models.CharField(blank=True, help_text="Optional PSOP/document identifier, e.g. STD-7100.", max_length=120)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("resolved_at", models.DateTimeField(blank=True, null=True)), ("closed_at", models.DateTimeField(blank=True, null=True)),
            ("assigned_department", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tickets", to="departments.department")),
            ("assigned_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tickets_assigned", to=settings.AUTH_USER_MODEL)),
            ("related_asset", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tickets", to="bam.asset")),
            ("requester", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tickets_requested", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering":["-created_at"]}),
        migrations.CreateModel(name="TicketComment", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("body", models.TextField()),
            ("visibility", models.CharField(choices=[("PUBLIC","Requester visible"),("INTERNAL","Internal note")], default="PUBLIC", max_length=12)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("author", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ticket_comments", to=settings.AUTH_USER_MODEL)), ("ticket", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="comments", to="shit.ticket")),
        ], options={"ordering":["created_at"]}),
        migrations.CreateModel(name="TicketAttachment", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("file", models.FileField(upload_to="shit/%Y/%m/")), ("original_filename", models.CharField(max_length=255)), ("mime_type", models.CharField(blank=True, max_length=120)), ("size_bytes", models.PositiveBigIntegerField(default=0)), ("sha256", models.CharField(blank=True, db_index=True, max_length=64)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("ticket", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attachments", to="shit.ticket")), ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ticket_attachments", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering":["-created_at"]}),
        migrations.CreateModel(name="TicketEvent", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("event_type", models.CharField(choices=[("CREATED","Created"),("COMMENTED","Commented"),("INTERNAL_NOTE","Internal note"),("ATTACHMENT_ADDED","Attachment added"),("STATUS_CHANGED","Status changed"),("SEVERITY_CHANGED","Severity changed"),("DEPARTMENT_CHANGED","Department changed"),("ASSIGNEE_CHANGED","Assignee changed"),("ASSET_LINKED","Asset linked"),("DOCUMENT_LINKED","Document linked")], max_length=32)),
            ("summary", models.CharField(max_length=240)), ("metadata", models.JSONField(blank=True, default=dict)), ("occurred_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ticket_events", to=settings.AUTH_USER_MODEL)), ("ticket", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="events", to="shit.ticket")),
        ], options={"ordering":["-occurred_at"]}),
        migrations.AddIndex(model_name="ticket", index=models.Index(fields=["assigned_department","status"], name="shit_ticket_assigne_9ca914_idx")),
        migrations.AddIndex(model_name="ticket", index=models.Index(fields=["assigned_user","status"], name="shit_ticket_assigne_13a4c2_idx")),
        migrations.AddIndex(model_name="ticket", index=models.Index(fields=["requester","status"], name="shit_ticket_request_2dcfd0_idx")),
        migrations.AddIndex(model_name="ticket", index=models.Index(fields=["severity","status"], name="shit_ticket_severit_52cc18_idx")),
    ]
