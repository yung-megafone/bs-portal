import uuid

from django.conf import settings
from django.db import models


class Punch(models.Model):
    """
    Immutable authoritative punch record.

    Punch rows are never edited to "fix" time. Corrections are appended through
    PunchCorrection and the latest correction determines the effective value.
    """

    class PunchType(models.TextChoices):
        IN = "IN", "Clock in"
        OUT = "OUT", "Clock out"

    class Source(models.TextChoices):
        PORTAL = "PORTAL", "B.S. Portal"
        IMPORT = "IMPORT", "Imported"
        API = "API", "API"
        TERMINAL = "TERMINAL", "Terminal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="timeclock_punches",
    )
    punch_type = models.CharField(max_length=8, choices=PunchType.choices)
    occurred_at = models.DateTimeField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="timeclock_punches_recorded",
    )
    source = models.CharField(
        max_length=16,
        choices=Source.choices,
        default=Source.PORTAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "created_at"]
        indexes = [
            models.Index(fields=["employee", "occurred_at"]),
            models.Index(fields=["employee", "punch_type"]),
        ]

    def __str__(self):
        return f"{self.employee} {self.punch_type} {self.occurred_at.isoformat()}"

    @property
    def latest_correction(self):
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("corrections")
        if prefetched is not None:
            return max(prefetched, key=lambda item: item.created_at, default=None)
        return self.corrections.order_by("-created_at").first()

    @property
    def effective_punch_type(self):
        correction = self.latest_correction
        return correction.corrected_punch_type if correction else self.punch_type

    @property
    def effective_occurred_at(self):
        correction = self.latest_correction
        return correction.corrected_occurred_at if correction else self.occurred_at

    @property
    def is_corrected(self):
        return self.latest_correction is not None


class PunchCorrection(models.Model):
    """
    Append-only correction to a Punch.

    Multiple corrections are allowed so later administrative corrections do not
    destroy prior correction history. The latest correction is effective.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    punch = models.ForeignKey(
        Punch,
        on_delete=models.PROTECT,
        related_name="corrections",
    )
    corrected_punch_type = models.CharField(
        max_length=8,
        choices=Punch.PunchType.choices,
    )
    corrected_occurred_at = models.DateTimeField()
    reason = models.TextField()
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="timeclock_corrections",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["punch", "created_at"]),
            models.Index(fields=["corrected_by", "created_at"]),
        ]

    def __str__(self):
        return f"Correction for {self.punch_id} by {self.corrected_by}"


class TimeclockEvent(models.Model):
    """Audit event for punch and administrative actions."""

    class EventType(models.TextChoices):
        CLOCK_IN = "CLOCK_IN", "Clocked in"
        CLOCK_OUT = "CLOCK_OUT", "Clocked out"
        CORRECTION = "CORRECTION", "Punch corrected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="timeclock_events_as_employee",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="timeclock_events_as_actor",
    )
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    punch = models.ForeignKey(
        Punch,
        on_delete=models.PROTECT,
        related_name="events",
    )
    summary = models.CharField(max_length=240)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["employee", "occurred_at"]),
            models.Index(fields=["actor", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.employee} / {self.event_type} / {self.occurred_at.isoformat()}"
