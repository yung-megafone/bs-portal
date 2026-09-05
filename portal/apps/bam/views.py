import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.shit.models import Ticket, TicketAssetLink
from apps.shit.permissions import can_view_ticket, filter_visible_tickets

from .forms import (
    AssetAllocationForm,
    AssetCheckoutActionForm,
    AssetCreateForm,
    AssetEditForm,
    AssetEvidenceForm,
    AssetRequestActionForm,
    AssetRequestCreateForm,
    AssetRequestItemForm,
    AssetHandoffForm,
    AssetSelfReleaseForm,
    AssetStatusForm,
    CustodyForm,
)
from .models import (
    Asset,
    AssetCheckout,
    AssetEvidence,
    AssetRequest,
    AssetRequestItem,
    AssetStatus,
    AssetType,
)
from .permissions import (
    can_manage_asset_request,
    can_manage_asset_request_department,
    can_view_asset_request,
    managed_department_ids,
)
from .services import (
    add_asset_request_item,
    add_evidence,
    allocate_request_item,
    assign_custody,
    cancel_asset_request,
    cancel_asset_request_item,
    change_asset_status,
    complete_asset_request,
    create_asset,
    create_asset_request,
    deny_asset_request,
    deny_asset_request_item,
    eligible_assets_for_item,
    handoff_checkout,
    issue_checkout,
    release_request_item,
    return_checkout,
    self_release_checkout,
    reconcile_asset_automation,
    update_asset_details,
    waitlist_position,
    waitlist_status_message,
)


@login_required
def asset_list(request):
    query = request.GET.get("q", "").strip()
    assets = Asset.objects.select_related("department", "asset_type", "status", "current_custodian")
    if query:
        assets = assets.filter(
            Q(asset_id__icontains=query)
            | Q(manufacturer__icontains=query)
            | Q(model__icontains=query)
            | Q(serial_number__icontains=query)
            | Q(notes__icontains=query)
        )
    context = {
        "assets": assets[:500],
        "query": query,
        "total_count": Asset.objects.count(),
        "types_count": AssetType.objects.filter(is_active=True).count(),
        "statuses": AssetStatus.objects.filter(is_active=True),
        "my_open_requests": AssetRequest.objects.filter(requester=request.user).exclude(
            status__in=[AssetRequest.Status.CANCELLED, AssetRequest.Status.DENIED, AssetRequest.Status.COMPLETED]
        ).count(),
    }
    return render(request, "bam/asset_list.html", context)


@login_required
def asset_create(request):
    if request.method == "POST":
        form = AssetCreateForm(request.POST, request.FILES)
        if form.is_valid():
            asset = create_asset(
                actor=request.user,
                department=form.cleaned_data["department"],
                asset_type=form.cleaned_data["asset_type"],
                status=form.cleaned_data["status"],
                ownership=form.cleaned_data["ownership"],
                manufacturer=form.cleaned_data["manufacturer"],
                model=form.cleaned_data["model"],
                serial_number=form.cleaned_data["serial_number"],
                custodian=form.cleaned_data["custodian"],
                acquired_at=form.cleaned_data["acquired_at"],
                notes=form.cleaned_data["notes"],
                preferred_suffix=form.cleaned_data.get("preferred_suffix"),
            )
            if form.cleaned_data.get("asset_photo"):
                add_evidence(
                    asset=asset,
                    uploaded_file=form.cleaned_data["asset_photo"],
                    kind=AssetEvidence.Kind.ASSET_PHOTO,
                    actor=request.user,
                )
            if form.cleaned_data.get("serial_evidence"):
                add_evidence(
                    asset=asset,
                    uploaded_file=form.cleaned_data["serial_evidence"],
                    kind=AssetEvidence.Kind.SERIAL,
                    actor=request.user,
                )
            requested = form.cleaned_data.get("preferred_suffix")
            if requested and asset.unique_hex != requested:
                messages.warning(request, f"Preferred suffix {requested} was unavailable; BAM assigned {asset.unique_hex} instead.")
            elif requested:
                messages.success(request, f"Preferred suffix {asset.unique_hex} assigned.")
            return redirect("bam:detail", asset_id=asset.asset_id)
    else:
        form = AssetCreateForm()
    return render(request, "bam/asset_form.html", {"form": form})


_BAM_REQUEST_REF_RE = re.compile(r"\bBAMR-\d{2}-[0-9A-F]{6}\b")


def _redact_restricted_bam_request_refs(text, visible_request_numbers):
    """Hide BAM request identifiers the current viewer is not authorized to open."""
    text = text or ""
    return _BAM_REQUEST_REF_RE.sub(
        lambda match: match.group(0)
        if match.group(0) in visible_request_numbers
        else "restricted BAM request",
        text,
    )


@login_required
def asset_detail(request, asset_id):
    asset = get_object_or_404(
        Asset.objects.select_related("department", "asset_type", "status", "current_custodian", "created_by"),
        asset_id=asset_id,
    )
    visible_tickets = filter_visible_tickets(Ticket.objects.all(), request.user)
    ticket_links = (
        TicketAssetLink.objects.filter(
            asset=asset,
            ticket_id__in=visible_tickets.values("pk"),
        )
        .select_related(
            "ticket",
            "ticket__assigned_department",
            "ticket__assigned_user",
            "created_by",
        )
        .order_by("-ticket__updated_at")[:100]
    )
    all_active_reservations = list(
        asset.allocated_request_items.filter(
            status__in=[AssetRequestItem.Status.ALLOCATED, AssetRequestItem.Status.CHECKED_OUT]
        )
        .select_related("request", "request__requester", "department", "asset_type")
        .order_by("request__requested_start", "created_at")[:100]
    )
    all_specific_waitlist = list(
        asset.preferred_request_items.filter(
            status=AssetRequestItem.Status.WAITLISTED,
            preference_mode=AssetRequestItem.PreferenceMode.REQUIRE,
        )
        .select_related("request", "request__requester")
        .order_by("request__created_at", "created_at")[:100]
    )
    active_reservations = [
        item for item in all_active_reservations
        if can_view_asset_request(request.user, item.request)
    ]
    specific_waitlist = [
        item for item in all_specific_waitlist
        if can_view_asset_request(request.user, item.request)
    ]
    for item in specific_waitlist:
        item.waitlist_position_value = waitlist_position(item)

    all_checkout_history = list(
        asset.checkouts.select_related(
            "request_item",
            "request_item__request",
            "request_item__request__requester",
            "custodian",
            "issued_by",
            "returned_by",
        )[:100]
    )
    visible_checkout_history = [
        row for row in all_checkout_history
        if can_view_asset_request(request.user, row.request_item.request)
    ]
    all_current_checkout = next((row for row in all_checkout_history if row.returned_at is None), None)
    current_checkout = (
        all_current_checkout
        if all_current_checkout and can_view_asset_request(request.user, all_current_checkout.request_item.request)
        else None
    )

    # Asset history and custody history are globally useful BAM audit records,
    # but their free-text summaries may contain BAMR identifiers. Keep the
    # audit record visible while redacting request identifiers the viewer could
    # not open directly. This prevents history text from becoming an indirect
    # authorization bypass.
    events = list(asset.events.select_related("actor")[:100])
    custody = list(asset.custody_history.select_related("custodian", "assigned_by")[:100])
    referenced_request_numbers = set()
    for event in events:
        referenced_request_numbers.update(_BAM_REQUEST_REF_RE.findall(event.summary or ""))
    for row in custody:
        referenced_request_numbers.update(_BAM_REQUEST_REF_RE.findall(row.reason or ""))

    visible_request_numbers = set()
    if referenced_request_numbers:
        referenced_requests = AssetRequest.objects.filter(
            request_number__in=referenced_request_numbers
        ).select_related("requester", "related_ticket")
        visible_request_numbers = {
            asset_request.request_number
            for asset_request in referenced_requests
            if can_view_asset_request(request.user, asset_request)
        }

    for event in events:
        event.display_summary = _redact_restricted_bam_request_refs(
            event.summary, visible_request_numbers
        )
    for row in custody:
        row.display_reason = _redact_restricted_bam_request_refs(
            row.reason, visible_request_numbers
        )

    return render(
        request,
        "bam/asset_detail.html",
        {
            "asset": asset,
            "events": events,
            "evidence": asset.evidence.select_related("uploaded_by")[:100],
            "custody": custody,
            "ticket_links": ticket_links,
            "active_reservations": active_reservations,
            "hidden_reservation_count": len(all_active_reservations) - len(active_reservations),
            "specific_waitlist": specific_waitlist,
            "hidden_waitlist_count": len(all_specific_waitlist) - len(specific_waitlist),
            "current_checkout": current_checkout,
            "can_self_release": bool(current_checkout and current_checkout.custodian_id == request.user.id),
            "self_release_form": AssetSelfReleaseForm() if current_checkout and current_checkout.custodian_id == request.user.id else None,
            "return_condition_choices": AssetCheckout.ReturnCondition.choices,
            "restricted_current_checkout": bool(all_current_checkout and current_checkout is None),
            "checkout_history": visible_checkout_history,
            "hidden_checkout_count": len(all_checkout_history) - len(visible_checkout_history),
            "status_form": AssetStatusForm(initial={"status": asset.status}),
            "evidence_form": AssetEvidenceForm(),
            "custody_form": CustodyForm(initial={"custodian": asset.current_custodian}),
        },
    )


@login_required
def asset_status(request, asset_id):
    asset = get_object_or_404(Asset.objects.select_related("status"), asset_id=asset_id)
    if request.method == "POST":
        form = AssetStatusForm(request.POST)
        if form.is_valid():
            change_asset_status(
                asset=asset,
                new_status=form.cleaned_data["status"],
                actor=request.user,
                reason=form.cleaned_data["reason"],
            )
            promoted, checkout = reconcile_asset_automation(asset=asset, fallback_actor=request.user)
            if checkout is not None:
                messages.success(request, f"{asset.asset_id} became available and was automatically assigned to {checkout.custodian}.")
            elif promoted:
                messages.success(request, f"{asset.asset_id} became available; {len(promoted)} queued request{' was' if len(promoted) == 1 else 's were'} promoted.")
    return redirect("bam:detail", asset_id=asset.asset_id)


@login_required
def evidence_add(request, asset_id):
    asset = get_object_or_404(Asset, asset_id=asset_id)
    if request.method == "POST":
        form = AssetEvidenceForm(request.POST, request.FILES)
        if form.is_valid():
            add_evidence(
                asset=asset,
                uploaded_file=form.cleaned_data["file"],
                kind=form.cleaned_data["kind"],
                actor=request.user,
                notes=form.cleaned_data["notes"],
            )
    return redirect("bam:detail", asset_id=asset.asset_id)


@login_required
def asset_edit(request, asset_id):
    asset = get_object_or_404(Asset, asset_id=asset_id)
    initial = {
        "ownership": asset.ownership,
        "manufacturer": asset.manufacturer,
        "model": asset.model,
        "serial_number": asset.serial_number,
        "acquired_at": asset.acquired_at,
        "notes": asset.notes,
        "automatic_allocation_enabled": asset.automatic_allocation_enabled,
        "allocation_hold": asset.allocation_hold,
        "allocation_hold_reason": asset.allocation_hold_reason,
    }
    if request.method == "POST":
        form = AssetEditForm(request.POST)
        if form.is_valid():
            update_asset_details(asset=asset, actor=request.user, **form.cleaned_data)
            promoted, checkout = reconcile_asset_automation(asset=asset, fallback_actor=request.user)
            if checkout is not None:
                messages.success(request, f"{asset.asset_id} is eligible again and was automatically assigned to {checkout.custodian}.")
            elif promoted:
                messages.success(request, f"{asset.asset_id} is eligible again; {len(promoted)} queued request{' was' if len(promoted) == 1 else 's were'} promoted.")
            return redirect("bam:detail", asset_id=asset.asset_id)
    else:
        form = AssetEditForm(initial=initial)
    return render(request, "bam/asset_edit.html", {"asset": asset, "form": form})


@login_required
def asset_custody(request, asset_id):
    asset = get_object_or_404(Asset, asset_id=asset_id)
    if request.method == "POST":
        form = CustodyForm(request.POST)
        if form.is_valid():
            assign_custody(asset=asset, custodian=form.cleaned_data["custodian"], actor=request.user, reason=form.cleaned_data["reason"])
            promoted, checkout = reconcile_asset_automation(asset=asset, fallback_actor=request.user)
            if checkout is not None:
                messages.success(request, f"{asset.asset_id} returned to stock and was automatically assigned to {checkout.custodian}.")
            elif promoted:
                messages.success(request, f"{asset.asset_id} returned to stock; {len(promoted)} queued request{' was' if len(promoted) == 1 else 's were'} promoted.")
    return redirect("bam:detail", asset_id=asset.asset_id)


# ---------------------------------------------------------------------------
# BAM asset requests / reservation queue
# ---------------------------------------------------------------------------


def _request_queryset():
    return AssetRequest.objects.select_related("requester", "related_ticket").prefetch_related(
        "items__department",
        "items__asset_type",
        "items__preferred_asset",
        "items__allocated_asset",
    )


def _checkout_queryset():
    return AssetCheckout.objects.select_related(
        "request_item",
        "request_item__request",
        "request_item__request__requester",
        "request_item__department",
        "asset",
        "asset__department",
        "asset__asset_type",
        "custodian",
        "issued_by",
        "returned_by",
    )


@login_required
def asset_checkout_list(request):
    scope = request.GET.get("scope", "my")
    managed_ids = managed_department_ids(request.user)
    can_manage_any = request.user.is_staff or request.user.is_superuser
    if managed_ids is not None:
        managed_ids = list(managed_ids)
        can_manage_any = can_manage_any or bool(managed_ids)

    checkouts = _checkout_queryset().filter(returned_at__isnull=True)
    if scope == "managed" and can_manage_any:
        if managed_ids is not None:
            checkouts = checkouts.filter(asset__department_id__in=managed_ids)
    else:
        scope = "my"
        checkouts = checkouts.filter(custodian=request.user)

    rows = list(checkouts.order_by("request_item__request__requested_end", "checked_out_at")[:250])
    overdue_count = sum(1 for row in rows if row.is_overdue)
    return render(
        request,
        "bam/checkout_list.html",
        {
            "checkouts": rows,
            "scope": scope,
            "can_manage_any": can_manage_any,
            "overdue_count": overdue_count,
            "self_release_form": AssetSelfReleaseForm(),
            "return_condition_choices": AssetCheckout.ReturnCondition.choices,
        },
    )


@login_required
def asset_request_list(request):
    scope = request.GET.get("scope", "my")
    managed_ids = managed_department_ids(request.user)
    can_manage_any = request.user.is_staff or request.user.is_superuser
    if managed_ids is not None:
        managed_ids = list(managed_ids)
        can_manage_any = can_manage_any or bool(managed_ids)

    requests = _request_queryset()
    if scope == "queue" and can_manage_any:
        if managed_ids is None:
            requests = requests.all()
        else:
            requests = requests.filter(items__department_id__in=managed_ids).distinct()
    else:
        scope = "my"
        requests = requests.filter(requester=request.user)

    request_rows = list(requests[:250])
    for row in request_rows:
        row.user_can_manage = can_manage_asset_request(request.user, row)

    return render(
        request,
        "bam/request_list.html",
        {
            "asset_requests": request_rows,
            "scope": scope,
            "can_manage_any": can_manage_any,
        },
    )


def _resolve_related_ticket_for_request(user, ticket_number):
    if not ticket_number:
        return None
    ticket = get_object_or_404(Ticket, ticket_number=ticket_number)
    if not can_view_ticket(user, ticket):
        raise PermissionDenied
    return ticket


@login_required
def asset_request_create(request, asset_id=None):
    asset = None
    if asset_id:
        asset = get_object_or_404(
            Asset.objects.select_related("department", "asset_type", "status", "current_custodian"),
            asset_id=asset_id,
        )
        if asset.status.is_terminal:
            messages.error(request, "Retired/disposed assets cannot accept new allocation requests.")
            return redirect("bam:detail", asset_id=asset.asset_id)
    related_ticket = _resolve_related_ticket_for_request(request.user, request.GET.get("ticket"))

    if request.method == "POST":
        form = AssetRequestCreateForm(request.POST, user=request.user, asset=asset, related_ticket=related_ticket)
        if form.is_valid():
            try:
                asset_request, item = create_asset_request(
                    actor=request.user,
                    purpose=form.cleaned_data["purpose"],
                    requested_start=form.cleaned_data["requested_start"],
                    requested_end=form.cleaned_data["requested_end"],
                    desired_completion_date=form.cleaned_data["desired_completion_date"],
                    justification=form.cleaned_data["justification"],
                    priority=form.cleaned_data["priority"],
                    related_ticket=form.cleaned_data["related_ticket"],
                    department=form.cleaned_data["department"],
                    asset_type=form.cleaned_data["asset_type"],
                    preference_mode=form.cleaned_data["preference_mode"],
                    preferred_asset=form.cleaned_data["preferred_asset"],
                    item_note=form.cleaned_data["item_note"],
                    apply_automation=True,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                item.refresh_from_db()
                if item.status == AssetRequestItem.Status.CHECKED_OUT:
                    messages.success(
                        request,
                        f"{asset_request.request_number} approved automatically; {item.allocated_asset.asset_id} assigned to you.",
                    )
                elif item.status == AssetRequestItem.Status.ALLOCATED:
                    messages.success(
                        request,
                        f"{asset_request.request_number} approved automatically; {item.allocated_asset.asset_id} reserved.",
                    )
                elif item.status == AssetRequestItem.Status.WAITLISTED:
                    messages.warning(
                        request,
                        f"{asset_request.request_number} submitted; no eligible asset is free, so the request entered the queue.",
                    )
                else:
                    messages.success(request, f"Asset request {asset_request.request_number} submitted for review.")
                return redirect("bam:request_detail", request_number=asset_request.request_number)
    else:
        form = AssetRequestCreateForm(user=request.user, asset=asset, related_ticket=related_ticket)

    return render(
        request,
        "bam/request_form.html",
        {"form": form, "source_asset": asset, "source_ticket": related_ticket},
    )


@login_required
def asset_request_detail(request, request_number):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    if not can_view_asset_request(request.user, asset_request):
        raise PermissionDenied

    can_manage = can_manage_asset_request(request.user, asset_request)
    visible_related_ticket = (
        asset_request.related_ticket
        if asset_request.related_ticket and can_view_ticket(request.user, asset_request.related_ticket)
        else None
    )
    related_ticket_restricted = bool(asset_request.related_ticket_id and visible_related_ticket is None)
    can_add_item = (
        asset_request.requester_id == request.user.id or can_manage
    ) and asset_request.status not in {
        AssetRequest.Status.DENIED,
        AssetRequest.Status.CANCELLED,
        AssetRequest.Status.COMPLETED,
    }

    items = list(asset_request.items.select_related(
        "department", "asset_type", "preferred_asset", "preferred_asset__status",
        "allocated_asset", "allocated_asset__status", "allocated_by",
    ))
    checkout_map = {
        checkout.request_item_id: checkout
        for checkout in AssetCheckout.objects.filter(request_item_id__in=[item.pk for item in items])
        .select_related(
            "request_item",
            "request_item__request",
            "custodian",
            "issued_by",
            "returned_by",
            "handoff_to",
        )
    }
    for item in items:
        item.waitlist_position_value = waitlist_position(item)
        item.eligible_count = (
            eligible_assets_for_item(item).count()
            if item.status not in {AssetRequestItem.Status.ALLOCATED, AssetRequestItem.Status.CHECKED_OUT}
            else 0
        )
        item.waitlist_status_message = waitlist_status_message(item)
        item.user_can_manage = can_manage_asset_request_department(request.user, item.department)
        item.allocation_form = AssetAllocationForm(item=item) if item.user_can_manage else None
        item.checkout_record = checkout_map.get(item.pk)
        item.checkout_form = AssetCheckoutActionForm() if item.user_can_manage else None
        item.handoff_form = (
            AssetHandoffForm(checkout=item.checkout_record)
            if item.user_can_manage and item.checkout_record and item.checkout_record.returned_at is None
            else None
        )
        item.handoff_candidate_count = (
            item.handoff_form.fields["next_item"].queryset.count()
            if item.handoff_form is not None
            else 0
        )

    return render(
        request,
        "bam/request_detail.html",
        {
            "asset_request": asset_request,
            "visible_related_ticket": visible_related_ticket,
            "related_ticket_restricted": related_ticket_restricted,
            "request_items": items,
            "events": asset_request.events.select_related("actor")[:100],
            "can_manage": can_manage,
            "can_add_item": can_add_item,
            "item_form": AssetRequestItemForm() if can_add_item else None,
            "action_form": AssetRequestActionForm(),
        },
    )


@login_required
@require_POST
def asset_request_item_add(request, request_number):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    if not (
        asset_request.requester_id == request.user.id
        or can_manage_asset_request(request.user, asset_request)
    ):
        raise PermissionDenied
    form = AssetRequestItemForm(request.POST)
    if form.is_valid():
        # A requester may expand their own request across departments. A
        # manager acting on somebody else's request may only add a requirement
        # for a department they are actually authorized to manage.
        if (
            asset_request.requester_id != request.user.id
            and not can_manage_asset_request_department(request.user, form.cleaned_data["department"])
        ):
            raise PermissionDenied
        try:
            add_asset_request_item(
                asset_request=asset_request,
                actor=request.user,
                department=form.cleaned_data["department"],
                asset_type=form.cleaned_data["asset_type"],
                preference_mode=form.cleaned_data["preference_mode"],
                preferred_asset=form.cleaned_data["preferred_asset"],
                note=form.cleaned_data["note"],
                apply_automation=True,
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Asset requirement added.")
    else:
        messages.error(request, "Could not add requirement. Check the selected asset and preference mode.")
    return redirect("bam:request_detail", request_number=request_number)


@login_required
@require_POST
def asset_request_item_deny(request, request_number, item_id):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    item = get_object_or_404(
        AssetRequestItem.objects.select_related("department", "asset_type", "request"),
        pk=item_id,
        request=asset_request,
    )
    if not can_manage_asset_request_department(request.user, item.department):
        raise PermissionDenied
    form = AssetRequestActionForm(request.POST)
    if form.is_valid():
        try:
            deny_asset_request_item(item=item, actor=request.user, reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Asset requirement denied.")
    return redirect("bam:request_detail", request_number=request_number)


@login_required
@require_POST
def asset_request_item_cancel(request, request_number, item_id):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    item = get_object_or_404(
        AssetRequestItem.objects.select_related("department", "asset_type", "request"),
        pk=item_id,
        request=asset_request,
    )
    if not (
        asset_request.requester_id == request.user.id
        or can_manage_asset_request_department(request.user, item.department)
    ):
        raise PermissionDenied
    if request.method == "POST":
        form = AssetRequestActionForm(request.POST)
        if form.is_valid():
            try:
                cancel_asset_request_item(item=item, actor=request.user, reason=form.cleaned_data["reason"])
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Asset requirement removed from the request.")
    return redirect("bam:request_detail", request_number=request_number)


@login_required
@require_POST
def asset_request_item_allocate(request, request_number, item_id):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    item = get_object_or_404(
        AssetRequestItem.objects.select_related("department", "asset_type", "preferred_asset", "request"),
        pk=item_id,
        request=asset_request,
    )
    if not can_manage_asset_request_department(request.user, item.department):
        raise PermissionDenied
    form = AssetAllocationForm(request.POST, item=item)
    if form.is_valid():
        try:
            result = allocate_request_item(
                item=item,
                actor=request.user,
                selected_asset=form.cleaned_data["allocated_asset"],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            if result.status == AssetRequestItem.Status.WAITLISTED:
                messages.warning(request, "No eligible asset is currently available; requirement placed in queue.")
            else:
                messages.success(request, f"Reserved {result.allocated_asset.asset_id}.")
    return redirect("bam:request_detail", request_number=request_number)


@login_required
@require_POST
def asset_request_item_release(request, request_number, item_id):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    item = get_object_or_404(AssetRequestItem.objects.select_related("department", "request"), pk=item_id, request=asset_request)
    if not can_manage_asset_request_department(request.user, item.department):
        raise PermissionDenied
    if request.method == "POST":
        form = AssetRequestActionForm(request.POST)
        if form.is_valid():
            try:
                _, promoted = release_request_item(item=item, actor=request.user, reason=form.cleaned_data["reason"])
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                message = "Reservation released."
                if promoted:
                    message += f" {len(promoted)} compatible waitlist entr{'y' if len(promoted) == 1 else 'ies'} promoted."
                messages.success(request, message)
    return redirect("bam:request_detail", request_number=request_number)


@login_required
@require_POST
def asset_request_item_checkout(request, request_number, item_id):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    item = get_object_or_404(
        AssetRequestItem.objects.select_related("department", "request", "allocated_asset"),
        pk=item_id,
        request=asset_request,
    )
    if not can_manage_asset_request_department(request.user, item.department):
        raise PermissionDenied
    form = AssetCheckoutActionForm(request.POST)
    if form.is_valid():
        try:
            checkout = issue_checkout(item=item, actor=request.user, notes=form.cleaned_data["reason"])
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"Checked out {checkout.asset.asset_id} to {checkout.custodian}.")
    return redirect("bam:request_detail", request_number=request_number)


@login_required
@require_POST
def asset_request_item_return(request, request_number, item_id):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    item = get_object_or_404(
        AssetRequestItem.objects.select_related("department", "request"),
        pk=item_id,
        request=asset_request,
    )
    if not can_manage_asset_request_department(request.user, item.department):
        raise PermissionDenied
    checkout = get_object_or_404(AssetCheckout, request_item=item, returned_at__isnull=True)
    form = AssetCheckoutActionForm(request.POST)
    if form.is_valid():
        try:
            _, promoted = return_checkout(checkout=checkout, actor=request.user, reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            message = "Asset returned and custody closed."
            if promoted:
                message += f" {len(promoted)} compatible waitlist entr{'y' if len(promoted) == 1 else 'ies'} promoted."
            messages.success(request, message)
    return redirect("bam:request_detail", request_number=request_number)


@login_required
@require_POST
def asset_request_item_handoff(request, request_number, item_id):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    item = get_object_or_404(
        AssetRequestItem.objects.select_related("department", "request"),
        pk=item_id,
        request=asset_request,
    )
    if not can_manage_asset_request_department(request.user, item.department):
        raise PermissionDenied
    checkout = get_object_or_404(AssetCheckout, request_item=item, returned_at__isnull=True)
    form = AssetHandoffForm(request.POST, checkout=checkout)
    if form.is_valid():
        target = form.cleaned_data["next_item"]
        if not can_manage_asset_request_department(request.user, target.department):
            raise PermissionDenied
        try:
            next_checkout = handoff_checkout(
                checkout=checkout,
                next_item=target,
                actor=request.user,
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(
                request,
                f"Direct handoff completed: {next_checkout.asset.asset_id} → {next_checkout.custodian}.",
            )
    else:
        messages.error(request, "Select an active approved reservation for the handoff.")
    return redirect("bam:request_detail", request_number=request_number)


@login_required
@require_POST
def asset_checkout_self_release(request, checkout_id):
    checkout = get_object_or_404(
        AssetCheckout.objects.select_related("asset", "custodian", "request_item", "request_item__request"),
        pk=checkout_id,
        returned_at__isnull=True,
    )
    if checkout.custodian_id != request.user.id:
        raise PermissionDenied
    form = AssetSelfReleaseForm(request.POST)
    if form.is_valid():
        try:
            returned, promoted, active_next = self_release_checkout(
                checkout=checkout,
                actor=request.user,
                condition=form.cleaned_data["condition"],
                notes=form.cleaned_data["notes"],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            if returned.return_condition != AssetCheckout.ReturnCondition.GOOD:
                messages.warning(
                    request,
                    f"{returned.asset.asset_id} released to stock with an allocation hold for follow-up.",
                )
            elif active_next is not None:
                messages.success(
                    request,
                    f"{returned.asset.asset_id} released and automatically assigned to {active_next.custodian}.",
                )
            elif promoted:
                messages.success(
                    request,
                    f"{returned.asset.asset_id} released; {len(promoted)} queued reservation{'s' if len(promoted) != 1 else ''} promoted.",
                )
            else:
                messages.success(request, f"{returned.asset.asset_id} released back to stock custody.")
    else:
        messages.error(request, "Choose the asset condition before releasing it.")
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("bam:checkout_list")


@login_required
@require_POST
def asset_request_cancel(request, request_number):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    if not (
        asset_request.requester_id == request.user.id
        or can_manage_asset_request(request.user, asset_request)
    ):
        raise PermissionDenied
    if request.method == "POST":
        form = AssetRequestActionForm(request.POST)
        if form.is_valid():
            try:
                cancel_asset_request(asset_request=asset_request, actor=request.user, reason=form.cleaned_data["reason"])
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Asset request cancelled.")
    return redirect("bam:request_detail", request_number=request_number)


@login_required
@require_POST
def asset_request_deny(request, request_number):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    if not can_manage_asset_request(request.user, asset_request):
        raise PermissionDenied
    if request.method == "POST":
        form = AssetRequestActionForm(request.POST)
        if form.is_valid():
            try:
                deny_asset_request(asset_request=asset_request, actor=request.user, reason=form.cleaned_data["reason"])
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Asset request denied.")
    return redirect("bam:request_detail", request_number=request_number)


@login_required
@require_POST
def asset_request_complete(request, request_number):
    asset_request = get_object_or_404(_request_queryset(), request_number=request_number)
    if not can_manage_asset_request(request.user, asset_request):
        raise PermissionDenied
    if request.method == "POST":
        form = AssetRequestActionForm(request.POST)
        if form.is_valid():
            try:
                complete_asset_request(asset_request=asset_request, actor=request.user, reason=form.cleaned_data["reason"])
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Asset request completed.")
    return redirect("bam:request_detail", request_number=request_number)
