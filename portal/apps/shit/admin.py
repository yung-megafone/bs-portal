from django.contrib import admin

from .models import (
    Ticket,
    TicketAssetLink,
    TicketAttachment,
    TicketComment,
    TicketEvent,
)


class TicketAssetLinkInline(admin.TabularInline):
    model = TicketAssetLink
    extra = 0
    autocomplete_fields = ("asset", "created_by")
    fields = (
        "asset",
        "relationship_type",
        "note",
        "created_by",
        "created_at",
    )
    readonly_fields = ("created_at",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_number",
        "title",
        "severity",
        "status",
        "assigned_department",
        "assigned_user",
        "requester",
        "created_at",
    )
    list_filter = ("severity", "status", "ticket_type", "assigned_department")
    search_fields = (
        "ticket_number",
        "title",
        "description",
        "related_document",
        "asset_links__asset__asset_id",
    )
    readonly_fields = (
        "ticket_number",
        "related_asset",
        "created_at",
        "updated_at",
        "resolved_at",
        "closed_at",
    )
    inlines = (TicketAssetLinkInline,)


@admin.register(TicketAssetLink)
class TicketAssetLinkAdmin(admin.ModelAdmin):
    list_display = (
        "ticket",
        "asset",
        "relationship_type",
        "created_by",
        "created_at",
    )
    list_filter = ("relationship_type",)
    search_fields = ("ticket__ticket_number", "asset__asset_id", "note")
    autocomplete_fields = ("ticket", "asset", "created_by")


admin.site.register(TicketComment)
admin.site.register(TicketAttachment)
admin.site.register(TicketEvent)
