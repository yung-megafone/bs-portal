from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.views import dashboard, health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("health/", health, name="health"),
    path("departments/", include("apps.departments.urls")),
    path("bam/", include("apps.bam.urls")),
    path("shit/", include("apps.shit.urls")),
    path("timeclock/", include("apps.timeclock.urls")),
    path("", dashboard, name="dashboard"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
