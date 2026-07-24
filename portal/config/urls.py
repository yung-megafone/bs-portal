from django.contrib import admin
from django.urls import include, path

from apps.core.views import dashboard, health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("health/", health, name="health"),
    path("departments/", include("apps.departments.urls")),
    path("", dashboard, name="dashboard"),
]
