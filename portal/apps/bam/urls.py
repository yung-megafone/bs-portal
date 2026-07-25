from django.urls import path

from . import views

app_name = "bam"

urlpatterns = [
    path("", views.asset_list, name="list"),
    path("new/", views.asset_create, name="create"),
    path("<str:asset_id>/", views.asset_detail, name="detail"),
    path("<str:asset_id>/edit/", views.asset_edit, name="edit"),
    path("<str:asset_id>/custody/", views.asset_custody, name="custody"),
    path("<str:asset_id>/status/", views.asset_status, name="status"),
    path("<str:asset_id>/evidence/", views.evidence_add, name="evidence_add"),
]
