import uuid

from django.conf import settings
from django.db import models


class Ticket(models.Model):
    class Type(models.TextChoices):
        INCIDENT = "INCIDENT", "Incident"
        REQUEST = "REQUEST", "Service request"
        ACCESS = "ACCESS", "Access request"
        CHANGE = "CHANGE", "Change request"
        PROBLEM = "PROBLEM", "Problem"
        PSOP = "PSOP", "PSOP / documentation"
        FEEDBACK = "FEEDBACK", "Feedback / note"
        OTHER = "OTHER", "Other"

    class Severity(models.TextChoices):
        NONE = "NONE", "NONE"
        SEV5 = "SEV5", "SEV-5"
        SEV4 = "SEV4", "SEV-4"
        SEV3 = "SEV3", "SEV-3"
        SEV2 = "SEV2", "SEV-2"
        SEV1 = "SEV1", "SEV-1"

    class Status(models.TextChoices):
        NEW = "NEW", "New"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        WAITING_REQUESTER = "WAITING_REQUESTER", "Waiting on requester"
        WAITING_VENDOR = "WAITING_VENDOR", "Waiting on vendor"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Human-readable immutable identifier. The database UNIQUE constraint is
    # authoritative for collision prevention.
    ticket_number = models.CharField(max_length=32, unique=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    ticket_type = models.CharField(
        max_length=24,
        choices=Type.choices,
        default=Type.REQUEST,
    )
    severity = models.CharField(
        max_length=8,
        choices=Severity.choices,
        default=Severity.SEV5,
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.NEW,
    )
    # Operational queue order for the board. Severity is deliberately separate.
    # New tickets default to zero so they naturally appear before manually ranked
    # tickets until an agent explicitly reorders the column.
    queue_position = models.PositiveIntegerField(default=0)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tickets_requested",
    )
    assigned_department = models.ForeignKey(
        "departments.Department",
        on_delete=models.PROTECT,
        related_name="tickets",
        null=True,
        blank=True,
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tickets_assigned",
        null=True,
        blank=True,
    )
    related_asset = models.ForeignKey(
        "bam.Asset",
        on_delete=models.PROTECT,
        related_name="tickets",
        null=True,
        blank=True,
    )
    related_document = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional PSOP/document identifier, e.g. STD-7100.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["assigned_department", "status"]),
            models.Index(fields=["assigned_user", "status"]),
            models.Index(fields=["requester", "status"]),
            models.Index(fields=["severity", "status"]),
            models.Index(
                fields=["status", "queue_position"],
                name="shit_tkt_status_queue_idx",
            ),
        ]

    def __str__(self):
        return f"{self.ticket_number} — {self.title}"


class TicketComment(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = "PUBLIC", "Requester visible"
        INTERNAL = "INTERNAL", "Internal note"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.PROTECT,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_comments",
    )
    body = models.TextField()
    visibility = models.CharField(
        max_length=12,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class TicketAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_attachments",
    )
    file = models.FileField(upload_to="shit/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class TicketEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "CREATED", "Created"
        COMMENTED = "COMMENTED", "Commented"
        INTERNAL_NOTE = "INTERNAL_NOTE", "Internal note"
        ATTACHMENT_ADDED = "ATTACHMENT_ADDED", "Attachment added"
        STATUS_CHANGED = "STATUS_CHANGED", "Status changed"
        SEVERITY_CHANGED = "SEVERITY_CHANGED", "Severity changed"
        DEPARTMENT_CHANGED = "DEPARTMENT_CHANGED", "Department changed"
        ASSIGNEE_CHANGED = "ASSIGNEE_CHANGED", "Assignee changed"
        ASSET_LINKED = "ASSET_LINKED", "Asset linked"
        DOCUMENT_LINKED = "DOCUMENT_LINKED", "Document linked"
        QUEUE_REORDERED = "QUEUE_REORDERED", "Queue reordered"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.PROTECT,
        related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_events",
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    summary = models.CharField(max_length=240)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
