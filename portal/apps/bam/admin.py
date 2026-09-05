from django.contrib import admin

from .models import (
    Asset,
    AssetCheckout,
    AssetCustody,
    AssetEvent,
    AssetEvidence,
    AssetRelationship,
    AssetRequest,
    AssetRequestEvent,
    AssetRequestItem,
    AssetStatus,
    AssetType,
    BAMAutomationSettings,
)


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")


@admin.register(AssetStatus)
class AssetStatusAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_terminal", "is_active", "sort_order")
    list_filter = ("is_terminal", "is_active")


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_id", "asset_type", "department", "status", "current_custodian", "automatic_allocation_enabled", "allocation_hold", "manufacturer", "model")
    list_filter = ("department", "asset_type", "status", "ownership", "automatic_allocation_enabled", "allocation_hold")
    search_fields = ("asset_id", "serial_number", "manufacturer", "model")
    readonly_fields = ("asset_id", "unique_hex", "created_at", "updated_at")


class AssetRequestItemInline(admin.TabularInline):
    model = AssetRequestItem
    extra = 0
    readonly_fields = ("allocated_at", "released_at", "created_at", "updated_at")


@admin.register(AssetRequest)
class AssetRequestAdmin(admin.ModelAdmin):
    list_display = ("request_number", "requester", "purpose", "priority", "status", "requested_start", "requested_end")
    list_filter = ("priority", "status", "requested_start")
    search_fields = ("request_number", "purpose", "justification", "requester__username", "related_ticket__ticket_number")
    readonly_fields = ("request_number", "created_at", "updated_at")
    inlines = (AssetRequestItemInline,)


@admin.register(AssetRequestItem)
class AssetRequestItemAdmin(admin.ModelAdmin):
    list_display = ("request", "department", "asset_type", "preference_mode", "preferred_asset", "allocated_asset", "status")
    list_filter = ("department", "asset_type", "preference_mode", "status")
    search_fields = ("request__request_number", "preferred_asset__asset_id", "allocated_asset__asset_id")


@admin.register(AssetRequestEvent)
class AssetRequestEventAdmin(admin.ModelAdmin):
    list_display = ("request", "event_type", "actor", "occurred_at", "summary")
    list_filter = ("event_type",)
    search_fields = ("request__request_number", "summary", "actor__username")
    readonly_fields = ("occurred_at",)


@admin.register(AssetCheckout)
class AssetCheckoutAdmin(admin.ModelAdmin):
    list_display = ("asset", "custodian", "request_item", "checked_out_at", "returned_at", "issued_by")
    list_filter = ("checked_out_at", "returned_at")
    search_fields = ("asset__asset_id", "custodian__username", "request_item__request__request_number")
    readonly_fields = (
        "request_item", "asset", "custodian", "issued_by", "checked_out_at",
        "returned_at", "returned_by", "return_reason", "return_condition", "return_notes",
        "handoff_to", "notes",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False



admin.site.register(AssetCustody)
admin.site.register(AssetEvent)
admin.site.register(AssetEvidence)
admin.site.register(AssetRelationship)


@admin.register(BAMAutomationSettings)
class BAMAutomationSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Stock custody", {"fields": ("default_custodian", "automation_actor")}),
        ("Automatic request handling", {"fields": (
            "auto_approve_available_requests",
            "allow_equivalent_substitution",
            "auto_transfer_on_approval",
        )}),
        ("Queue and release automation", {"fields": (
            "auto_promote_waitlist",
            "auto_transfer_on_release",
        )}),
        ("Metadata", {"fields": ("updated_at",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not BAMAutomationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
