from django.urls import path

from . import views

app_name = "bam"

urlpatterns = [
    path("", views.asset_list, name="list"),
    path("new/", views.asset_create, name="create"),

    # Asset request / reservation queue. Keep these before <asset_id>/ so the
    # literal "requests" segment is never interpreted as an asset identifier.
    path("requests/", views.asset_request_list, name="request_list"),
    path("checkouts/", views.asset_checkout_list, name="checkout_list"),
    path("checkouts/<uuid:checkout_id>/release/", views.asset_checkout_self_release, name="checkout_self_release"),
    path("requests/new/", views.asset_request_create, name="request_create"),
    path("requests/<str:request_number>/", views.asset_request_detail, name="request_detail"),
    path("requests/<str:request_number>/items/add/", views.asset_request_item_add, name="request_item_add"),
    path("requests/<str:request_number>/items/<uuid:item_id>/allocate/", views.asset_request_item_allocate, name="request_item_allocate"),
    path("requests/<str:request_number>/items/<uuid:item_id>/cancel/", views.asset_request_item_cancel, name="request_item_cancel"),
    path("requests/<str:request_number>/items/<uuid:item_id>/deny/", views.asset_request_item_deny, name="request_item_deny"),
    path("requests/<str:request_number>/items/<uuid:item_id>/release/", views.asset_request_item_release, name="request_item_release"),
    path("requests/<str:request_number>/items/<uuid:item_id>/checkout/", views.asset_request_item_checkout, name="request_item_checkout"),
    path("requests/<str:request_number>/items/<uuid:item_id>/return/", views.asset_request_item_return, name="request_item_return"),
    path("requests/<str:request_number>/items/<uuid:item_id>/handoff/", views.asset_request_item_handoff, name="request_item_handoff"),
    path("requests/<str:request_number>/cancel/", views.asset_request_cancel, name="request_cancel"),
    path("requests/<str:request_number>/deny/", views.asset_request_deny, name="request_deny"),
    path("requests/<str:request_number>/complete/", views.asset_request_complete, name="request_complete"),

    path("<str:asset_id>/request/", views.asset_request_create, name="request_asset"),
    path("<str:asset_id>/", views.asset_detail, name="detail"),
    path("<str:asset_id>/edit/", views.asset_edit, name="edit"),
    path("<str:asset_id>/custody/", views.asset_custody, name="custody"),
    path("<str:asset_id>/status/", views.asset_status, name="status"),
    path("<str:asset_id>/evidence/", views.evidence_add, name="evidence_add"),
]
