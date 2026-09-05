import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


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
    automatic_allocation_enabled = models.BooleanField(
        default=True,
        help_text="Allow BAM automation to reserve/issue this asset when policy permits.",
    )
    allocation_hold = models.BooleanField(
        default=False,
        help_text="Temporarily exclude this asset from automatic allocation.",
    )
    allocation_hold_reason = models.CharField(max_length=240, blank=True)
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
        RESERVATION_ALLOCATED = "RESERVATION_ALLOCATED", "Reservation allocated"
        RESERVATION_RELEASED = "RESERVATION_RELEASED", "Reservation released"
        CHECKOUT_ISSUED = "CHECKOUT_ISSUED", "Checkout issued"
        CHECKOUT_RETURNED = "CHECKOUT_RETURNED", "Checkout returned"
        CHECKOUT_HANDOFF = "CHECKOUT_HANDOFF", "Checkout handed off"

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


class AssetRequest(models.Model):
    class Priority(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        TIME_SENSITIVE = "TIME_SENSITIVE", "Time-sensitive"
        CRITICAL_DEPENDENCY = "CRITICAL_DEPENDENCY", "Critical dependency"

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        QUEUED = "QUEUED", "Queued"
        PARTIALLY_RESERVED = "PARTIALLY_RESERVED", "Partially reserved"
        RESERVED = "RESERVED", "Reserved"
        PARTIALLY_CHECKED_OUT = "PARTIALLY_CHECKED_OUT", "Partially checked out"
        CHECKED_OUT = "CHECKED_OUT", "Checked out"
        DENIED = "DENIED", "Denied"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_number = models.CharField(max_length=32, unique=True, editable=False)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bam_asset_requests",
    )
    related_ticket = models.ForeignKey(
        "shit.Ticket",
        on_delete=models.PROTECT,
        related_name="asset_requests",
        null=True,
        blank=True,
    )
    purpose = models.CharField(max_length=200)
    justification = models.TextField(blank=True)
    priority = models.CharField(
        max_length=24,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    requested_start = models.DateField()
    requested_end = models.DateField()
    desired_completion_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["requester", "status"], name="bam_req_requester_status_idx"),
            models.Index(fields=["status", "requested_start"], name="bam_req_status_start_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(requested_end__gte=models.F("requested_start")),
                name="bam_request_end_not_before_start",
            ),
            models.CheckConstraint(
                condition=Q(desired_completion_date__isnull=True) | Q(desired_completion_date__gte=models.F("requested_start")),
                name="bam_request_due_not_before_start",
            ),
        ]

    def __str__(self):
        return f"{self.request_number} — {self.purpose}"


class AssetRequestItem(models.Model):
    class PreferenceMode(models.TextChoices):
        ANY = "ANY", "Any suitable asset"
        PREFER = "PREFER", "Prefer this asset; allow equivalent"
        REQUIRE = "REQUIRE", "Require this exact asset"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending review"
        WAITLISTED = "WAITLISTED", "Waitlisted"
        ALLOCATED = "ALLOCATED", "Reserved"
        CHECKED_OUT = "CHECKED_OUT", "Checked out"
        RETURNED = "RETURNED", "Returned"
        RELEASED = "RELEASED", "Released"
        DENIED = "DENIED", "Denied"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(
        AssetRequest,
        on_delete=models.PROTECT,
        related_name="items",
    )
    department = models.ForeignKey(
        "departments.Department",
        on_delete=models.PROTECT,
        related_name="asset_request_items",
    )
    asset_type = models.ForeignKey(
        AssetType,
        on_delete=models.PROTECT,
        related_name="request_items",
    )
    preference_mode = models.CharField(
        max_length=12,
        choices=PreferenceMode.choices,
        default=PreferenceMode.ANY,
    )
    preferred_asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="preferred_request_items",
        null=True,
        blank=True,
    )
    allocated_asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="allocated_request_items",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    note = models.CharField(max_length=240, blank=True)
    allocated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bam_allocations_made",
        null=True,
        blank=True,
    )
    allocated_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["department", "asset_type", "status"], name="bam_reqitem_pool_status_idx"),
            models.Index(fields=["preferred_asset", "status"], name="bam_reqitem_pref_status_idx"),
            models.Index(fields=["allocated_asset", "status"], name="bam_reqitem_alloc_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(preference_mode="ANY") | Q(preferred_asset__isnull=False),
                name="bam_reqitem_preferred_when_specific",
            ),
            models.CheckConstraint(
                condition=~Q(status__in=["ALLOCATED", "CHECKED_OUT", "RETURNED", "RELEASED"]) | Q(allocated_asset__isnull=False),
                name="bam_reqitem_allocated_has_asset",
            ),
            models.CheckConstraint(
                condition=Q(released_at__isnull=True) | Q(allocated_at__isnull=True) | Q(released_at__gte=models.F("allocated_at")),
                name="bam_reqitem_release_after_alloc",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.preference_mode in {self.PreferenceMode.PREFER, self.PreferenceMode.REQUIRE} and self.preferred_asset_id is None:
            errors["preferred_asset"] = "A preferred asset is required for this allocation mode."
        if self.preferred_asset_id:
            if self.department_id and self.preferred_asset.department_id != self.department_id:
                errors["preferred_asset"] = "Preferred asset must belong to the requested department."
            if self.asset_type_id and self.preferred_asset.asset_type_id != self.asset_type_id:
                errors["preferred_asset"] = "Preferred asset must match the requested asset type."
        if self.allocated_asset_id:
            if self.department_id and self.allocated_asset.department_id != self.department_id:
                errors["allocated_asset"] = "Reserved asset must belong to the requested department."
            if self.asset_type_id and self.allocated_asset.asset_type_id != self.asset_type_id:
                errors["allocated_asset"] = "Reserved asset must match the requested asset type."
            if (
                self.preference_mode == self.PreferenceMode.REQUIRE
                and self.preferred_asset_id
                and self.allocated_asset_id != self.preferred_asset_id
            ):
                errors["allocated_asset"] = "Exact-asset requests cannot be fulfilled by a substitute."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.request.request_number}: {self.department.code}/{self.asset_type.code}"


class AssetCheckout(models.Model):
    """Physical custody issued from an approved BAM reservation.

    Reservations answer whether an asset is committed for a date window.
    Checkouts answer who physically has the asset right now. Keeping this as a
    separate record preserves a complete handoff/return history without
    overloading AssetRequestItem or AssetCustody.
    """

    class ReturnCondition(models.TextChoices):
        GOOD = "GOOD", "Good / ready for next user"
        MINOR_ISSUE = "MINOR_ISSUE", "Minor issue"
        DAMAGED = "DAMAGED", "Damaged"
        MISSING_ACCESSORY = "MISSING_ACCESSORY", "Missing accessory"
        NEEDS_ATTENTION = "NEEDS_ATTENTION", "Needs attention"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_item = models.OneToOneField(
        AssetRequestItem,
        on_delete=models.PROTECT,
        related_name="checkout",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="checkouts",
    )
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bam_checkouts",
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bam_checkouts_issued",
    )
    checked_out_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bam_checkouts_returned",
        null=True,
        blank=True,
    )
    return_reason = models.CharField(max_length=240, blank=True)
    return_condition = models.CharField(
        max_length=24,
        choices=ReturnCondition.choices,
        default=ReturnCondition.GOOD,
    )
    return_notes = models.CharField(max_length=240, blank=True)
    handoff_to = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        related_name="handoff_from",
        null=True,
        blank=True,
    )
    notes = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-checked_out_at"]
        indexes = [
            models.Index(fields=["asset", "returned_at"], name="bam_checkout_asset_open_idx"),
            models.Index(fields=["custodian", "returned_at"], name="bam_checkout_cust_open_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(returned_at__isnull=True) | Q(returned_at__gte=models.F("checked_out_at")),
                name="bam_checkout_return_after_issue",
            ),
        ]

    @property
    def is_active(self):
        return self.returned_at is None

    @property
    def due_date(self):
        return self.request_item.request.requested_end

    @property
    def is_overdue(self):
        return self.is_active and self.due_date < timezone.localdate()

    @property
    def overdue_days(self):
        if not self.is_overdue:
            return 0
        return (timezone.localdate() - self.due_date).days

    def __str__(self):
        state = "active" if self.is_active else "returned"
        return f"{self.asset.asset_id} → {self.custodian} ({state})"


class BAMAutomationSettings(models.Model):
    """Singleton policy for BAM request/custody automation.

    The row with pk=1 is authoritative. If no explicit default custodian exists,
    services also look for an active user named ``vanguard`` as a bootstrap
    convenience.
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    default_custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bam_default_custodian_settings",
        null=True,
        blank=True,
        help_text="Stock/default custodian used when an asset is not issued to a requester.",
    )
    automation_actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bam_automation_actor_settings",
        null=True,
        blank=True,
        help_text="Audit actor for automatic BAM actions. Defaults to the stock custodian when unset.",
    )
    auto_approve_available_requests = models.BooleanField(default=True)
    auto_transfer_on_approval = models.BooleanField(
        default=True,
        help_text="Immediately issue custody when an automatically approved reservation is active today.",
    )
    auto_promote_waitlist = models.BooleanField(default=True)
    auto_transfer_on_release = models.BooleanField(
        default=True,
        help_text="After a good-condition release, issue an active promoted/approved reservation automatically.",
    )
    allow_equivalent_substitution = models.BooleanField(
        default=True,
        help_text="For 'prefer' requests, automation may choose another eligible equivalent when the preferred asset is busy.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "BAM automation settings"
        verbose_name_plural = "BAM automation settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "BAM automation settings"


class AssetRequestEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "CREATED", "Created"
        ITEM_ADDED = "ITEM_ADDED", "Requirement added"
        WAITLISTED = "WAITLISTED", "Waitlisted"
        ALLOCATED = "ALLOCATED", "Reserved"
        PROMOTED = "PROMOTED", "Queue promoted"
        CHECKED_OUT = "CHECKED_OUT", "Checked out"
        RETURNED = "RETURNED", "Returned"
        HANDOFF = "HANDOFF", "Direct handoff"
        RELEASED = "RELEASED", "Reservation released"
        DENIED = "DENIED", "Denied"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(
        AssetRequest,
        on_delete=models.PROTECT,
        related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bam_asset_request_events",
    )
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    occurred_at = models.DateTimeField(auto_now_add=True)
    summary = models.CharField(max_length=240)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"{self.request.request_number}: {self.get_event_type_display()}"
