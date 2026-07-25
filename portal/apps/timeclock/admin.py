from django.contrib import admin

from .models import Punch, PunchCorrection, TimeclockEvent


@admin.register(Punch)
class PunchAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "punch_type",
        "occurred_at",
        "source",
        "recorded_by",
        "created_at",
    )
    list_filter = ("punch_type", "source", "created_at")
    search_fields = ("employee__username", "employee__display_name")
    readonly_fields = (
        "id",
        "employee",
        "punch_type",
        "occurred_at",
        "recorded_by",
        "source",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PunchCorrection)
class PunchCorrectionAdmin(admin.ModelAdmin):
    list_display = (
        "punch",
        "corrected_punch_type",
        "corrected_occurred_at",
        "corrected_by",
        "created_at",
    )
    readonly_fields = (
        "id",
        "punch",
        "corrected_punch_type",
        "corrected_occurred_at",
        "reason",
        "corrected_by",
        "created_at",
    )

    def has_add_permission(self, request):
        # Corrections must use the Portal workflow so actor/reason/audit are
        # always recorded together.
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TimeclockEvent)
class TimeclockEventAdmin(admin.ModelAdmin):
    list_display = ("employee", "event_type", "actor", "occurred_at")
    list_filter = ("event_type", "occurred_at")
    search_fields = ("employee__username", "actor__username", "summary")
    readonly_fields = (
        "id",
        "employee",
        "actor",
        "event_type",
        "punch",
        "summary",
        "metadata",
        "occurred_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
