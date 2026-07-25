from django.contrib import admin

from .models import Asset, AssetCustody, AssetEvent, AssetEvidence, AssetRelationship, AssetStatus, AssetType


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
    list_display = ("asset_id", "asset_type", "department", "status", "current_custodian", "manufacturer", "model")
    list_filter = ("department", "asset_type", "status", "ownership")
    search_fields = ("asset_id", "serial_number", "manufacturer", "model")
    readonly_fields = ("asset_id", "unique_hex", "created_at", "updated_at")


admin.site.register(AssetCustody)
admin.site.register(AssetEvent)
admin.site.register(AssetEvidence)
admin.site.register(AssetRelationship)
