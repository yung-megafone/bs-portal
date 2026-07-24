from django.contrib import admin

from .models import Department, DepartmentMembership


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(DepartmentMembership)
class DepartmentMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "department", "role", "is_active", "started_at", "ended_at")
    list_filter = ("role", "is_active", "department")
    search_fields = ("user__username", "user__display_name", "department__code", "department__name")
