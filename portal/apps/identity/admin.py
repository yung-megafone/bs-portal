from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class PortalUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("B.S. Portal", {"fields": ("display_name",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("B.S. Portal", {"fields": ("display_name",)}),)
    list_display = ("username", "display_name", "email", "is_staff", "is_active")
