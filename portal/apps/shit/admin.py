from django.contrib import admin

from .models import Ticket, TicketAttachment, TicketComment, TicketEvent


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
        "related_asset__asset_id",
    )
    readonly_fields = (
        "ticket_number",
        "created_at",
        "updated_at",
        "resolved_at",
        "closed_at",
    )


admin.site.register(TicketComment)
admin.site.register(TicketAttachment)
admin.site.register(TicketEvent)