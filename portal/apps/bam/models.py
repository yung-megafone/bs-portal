import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q


code_validator = RegexValidator(
    regex=r"^[A-Z0-9]+$",
    message="Codes may contain only uppercase letters and numbers.",
)
hex_validator = RegexValidator(
    regex=r"^[0-9A-F]{4}$",
    message="Asset unique suffix must be exactly four hexadecimal characters.",
)


class AssetType(models.Model):
    code = models.CharField(max_length=8, unique=True, validators=[code_validator])
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class AssetStatus(models.Model):
    code = models.CharField(max_length=24, unique=True, validators=[code_validator])
    name = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    is_terminal = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "code"]

    def __str__(self):
        return self.name


class Asset(models.Model):
    class Ownership(models.TextChoices):
        COMPANY = "COMPANY", "Company"
        MANAGED_PERSONAL = "MANAGED_PERSONAL", "Managed personal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset_id = models.CharField(max_length=80, unique=True, editable=False)
    organization_code = models.CharField(max_length=12, default="BS", validators=[code_validator])
    unique_hex = models.CharField(max_length=4, validators=[hex_validator], editable=False)
    department = models.ForeignKey(
        "departments.Department",
        on_delete=models.PROTECT,
        related_name="assets",
    )
    asset_type = models.ForeignKey(
        AssetType,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    ownership = models.CharField(max_length=24, choices=Ownership.choices, default=Ownership.COMPANY)
    manufacturer = models.CharField(max_length=120, blank=True)
    model = models.CharField(max_length=160, blank=True)
    serial_number = models.CharField(max_length=200, blank=True)
    status = models.ForeignKey(
        AssetStatus,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    current_custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assets_in_custody",
        null=True,
        blank=True,
    )
    acquired_at = models.DateField(null=True, blank=True)
    retired_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assets_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset_id"]
        indexes = [
            models.Index(fields=["department", "status"]),
            models.Index(fields=["asset_type", "status"]),
            models.Index(fields=["serial_number"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization_code", "department", "asset_type", "unique_hex"],
                name="unique_asset_namespace_suffix",
            ),
            models.CheckConstraint(
                condition=Q(retired_at__isnull=True) | Q(acquired_at__isnull=True) | Q(retired_at__gte=models.F("acquired_at")),
                name="asset_retired_not_before_acquired",
            ),
        ]

    def __str__(self):
        return self.asset_id


class AssetCustody(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="custody_history")
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asset_custody_history",
    )
    assigned_at = models.DateTimeField()
    returned_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asset_custody_assignments",
    )
    reason = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-assigned_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(returned_at__isnull=True) | Q(returned_at__gte=models.F("assigned_at")),
                name="custody_return_not_before_assignment",
            )
        ]

    def __str__(self):
        return f"{self.asset.asset_id} → {self.custodian}"


class AssetEvent(models.Model):
    class EventType(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        UPDATED = "UPDATED", "Updated"
        STATUS_CHANGED = "STATUS_CHANGED", "Status changed"
        CUSTODY_ASSIGNED = "CUSTODY_ASSIGNED", "Custody assigned"
        CUSTODY_RETURNED = "CUSTODY_RETURNED", "Custody returned"
        EVIDENCE_ADDED = "EVIDENCE_ADDED", "Evidence added"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asset_events",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)
    summary = models.CharField(max_length=240)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"{self.asset.asset_id}: {self.get_event_type_display()}"


class AssetEvidence(models.Model):
    class Kind(models.TextChoices):
        ASSET_PHOTO = "ASSET_PHOTO", "Asset photo"
        SERIAL = "SERIAL", "Serial evidence"
        RECEIPT = "RECEIPT", "Receipt / proof of purchase"
        WARRANTY = "WARRANTY", "Warranty"
        INSPECTION = "INSPECTION", "Inspection evidence"
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="evidence")
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.OTHER)
    file = models.FileField(upload_to="bam/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asset_evidence_uploaded",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.asset.asset_id}: {self.get_kind_display()}"


class AssetRelationship(models.Model):
    class RelationshipType(models.TextChoices):
        COMPONENT_OF = "COMPONENT_OF", "Component of"
        ACCESSORY_TO = "ACCESSORY_TO", "Accessory to"
        REPLACES = "REPLACES", "Replaces"
        RELATED = "RELATED", "Related"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent_asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="child_relationships")
    child_asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="parent_relationships")
    relationship_type = models.CharField(max_length=24, choices=RelationshipType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["parent_asset", "child_asset", "relationship_type"],
                name="unique_asset_relationship",
            ),
            models.CheckConstraint(
                condition=~Q(parent_asset=models.F("child_asset")),
                name="asset_relationship_not_self",
            ),
        ]
