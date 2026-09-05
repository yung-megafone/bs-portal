from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.browser_preferences import get_preference, set_preference_cookie
from apps.bam.permissions import can_view_asset_request

from .forms import (
    TicketAssetLinkEditForm,
    TicketAssetLinkForm,
    TicketAttachmentForm,
    TicketBoardMoveForm,
    TicketCommentForm,
    TicketCreateForm,
    TicketManageForm,
)
from .models import Ticket, TicketAssetLink, TicketComment
from .permissions import can_manage_ticket, can_view_ticket, filter_visible_tickets
from .services import (
    add_attachment,
    add_comment,
    add_ticket_asset_link,
    create_ticket,
    move_ticket_on_board,
    remove_ticket_asset_link,
    update_ticket,
    update_ticket_asset_link,
)


SHIT_VIEW_PREFERENCE = "shit-view"
SHIT_DETAIL_DENSITY_PREFERENCE = "shit-detail-density"
SHIT_VIEW_MODES = {"list", "board"}
SHIT_DETAIL_DENSITIES = {"dense", "compact"}


TICKET_SELECT_RELATED = (
    "requester",
    "assigned_department",
    "assigned_user",
)

TICKET_ASSET_LINKS_PREFETCH = Prefetch(
    "asset_links",
    queryset=TicketAssetLink.objects.select_related(
        "asset",
        "asset__department",
        "asset__asset_type",
        "asset__status",
        "asset__current_custodian",
        "created_by",
    ).order_by("created_at"),
)


def _ticket_queryset():
    return Ticket.objects.select_related(*TICKET_SELECT_RELATED).prefetch_related(
        TICKET_ASSET_LINKS_PREFETCH
    )


def _visible_tickets(user):
    return filter_visible_tickets(_ticket_queryset(), user)


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _manage_ticket_or_forbidden(request, ticket_number):
    ticket = get_object_or_404(_ticket_queryset(), ticket_number=ticket_number)
    if not can_manage_ticket(request.user, ticket):
        return ticket, HttpResponseForbidden(
            "You do not have permission to manage this ticket."
        )
    return ticket, None


@login_required
def ticket_list(request):
    scope = request.GET.get("scope", "mine")
    query = request.GET.get("q", "").strip()

    requested_view_mode = request.GET.get("view")
    if requested_view_mode in SHIT_VIEW_MODES:
        view_mode = requested_view_mode
    else:
        # Board is the default for a browser with no saved preference. An
        # explicit List/Board selection is persisted client-side and mirrored
        # in a non-sensitive preference cookie so the server can render the
        # correct view immediately on the next visit.
        view_mode = get_preference(
            request,
            SHIT_VIEW_PREFERENCE,
            allowed=SHIT_VIEW_MODES,
            default="board",
        )

    active_department_ids = set(
        request.user.department_memberships.filter(is_active=True).values_list(
            "department_id",
            flat=True,
        )
    )

    tickets = _visible_tickets(request.user)
    if scope == "mine":
        tickets = tickets.filter(
            Q(requester=request.user) | Q(assigned_user=request.user)
        )
    elif scope == "department":
        tickets = tickets.filter(assigned_department_id__in=active_department_ids)
    elif scope == "all" and not (
        request.user.is_staff or request.user.is_superuser
    ):
        scope = "mine"
        tickets = tickets.filter(
            Q(requester=request.user) | Q(assigned_user=request.user)
        )

    if query:
        tickets = tickets.filter(
            Q(ticket_number__icontains=query)
            | Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(related_document__icontains=query)
            | Q(asset_links__asset__asset_id__icontains=query)
            | Q(asset_links__asset__manufacturer__icontains=query)
            | Q(asset_links__asset__model__icontains=query)
        ).distinct()

    context = {
        "scope": scope,
        "query": query,
        "view_mode": view_mode,
        "status_choices": list(Ticket.Status.choices),
    }

    if view_mode == "board":
        board_tickets = list(
            tickets.order_by("queue_position", "-created_at", "ticket_number")[:500]
        )
        is_global_agent = request.user.is_staff or request.user.is_superuser
        for ticket in board_tickets:
            ticket.board_can_manage = bool(
                is_global_agent
                or ticket.assigned_user_id == request.user.id
                or ticket.assigned_department_id in active_department_ids
            )

        columns = [
            {"status": status, "label": label, "tickets": []}
            for status, label in Ticket.Status.choices
        ]
        columns_by_status = {column["status"]: column for column in columns}
        for ticket in board_tickets:
            columns_by_status[ticket.status]["tickets"].append(ticket)

        context["board_columns"] = columns
        context["ticket_count"] = len(board_tickets)
    else:
        context["tickets"] = tickets[:500]

    response = render(request, "shit/ticket_list.html", context)
    if requested_view_mode in SHIT_VIEW_MODES:
        set_preference_cookie(
            response,
            request,
            SHIT_VIEW_PREFERENCE,
            requested_view_mode,
        )
    return response


@login_required
def ticket_create(request):
    if request.method == "POST":
        form = TicketCreateForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = create_ticket(
                actor=request.user,
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                ticket_type=form.cleaned_data["ticket_type"],
                severity=form.cleaned_data["severity"],
                assigned_department=form.cleaned_data["assigned_department"],
                related_assets=form.cleaned_data["related_assets"],
                asset_relationship=form.cleaned_data["asset_relationship"],
                related_document=form.cleaned_data["related_document"],
            )
            if form.cleaned_data.get("attachment"):
                add_attachment(
                    ticket=ticket,
                    actor=request.user,
                    uploaded_file=form.cleaned_data["attachment"],
                )
            messages.success(request, f"{ticket.ticket_number} created.")
            return redirect("shit:detail", ticket_number=ticket.ticket_number)
    else:
        form = TicketCreateForm()
    return render(request, "shit/ticket_form.html", {"form": form})


@login_required
def ticket_detail(request, ticket_number):
    ticket = get_object_or_404(
        _ticket_queryset(),
        ticket_number=ticket_number,
    )
    if not can_view_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have access to this ticket.")
    manage = can_manage_ticket(request.user, ticket)
    comments = ticket.comments.select_related("author")
    if not manage:
        comments = comments.filter(visibility=TicketComment.Visibility.PUBLIC)

    asset_links = list(ticket.asset_links.all())
    visible_asset_requests = [
        asset_request
        for asset_request in ticket.asset_requests.select_related("requester").prefetch_related(
            "items__department", "items__asset_type", "items__preferred_asset", "items__allocated_asset"
        ).order_by("-created_at")[:100]
        if can_view_asset_request(request.user, asset_request)
    ]
    return render(
        request,
        "shit/ticket_detail.html",
        {
            "ticket": ticket,
            "asset_links": asset_links,
            "asset_link_count": len(asset_links),
            "asset_requests": visible_asset_requests,
            "asset_request_count": len(visible_asset_requests),
            "can_manage": manage,
            "comments": comments,
            "events": ticket.events.select_related("actor")[:200] if manage else [],
            "attachments": ticket.attachments.select_related("uploaded_by")[:100],
            "comment_form": TicketCommentForm(),
            "attachment_form": TicketAttachmentForm(),
            "asset_link_form": TicketAssetLinkForm(ticket=ticket) if manage else None,
            "asset_relationship_choices": TicketAssetLink.RelationshipType.choices,
            "detail_density_preference": get_preference(
                request,
                SHIT_DETAIL_DENSITY_PREFERENCE,
                allowed=SHIT_DETAIL_DENSITIES,
                default="",
            ),
            "manage_form": (
                TicketManageForm(
                    initial={
                        "status": ticket.status,
                        "severity": ticket.severity,
                        "assigned_department": ticket.assigned_department,
                        "assigned_user": ticket.assigned_user,
                        "related_document": ticket.related_document,
                    }
                )
                if manage
                else None
            ),
        },
    )


@login_required
def ticket_manage(request, ticket_number):
    ticket, forbidden = _manage_ticket_or_forbidden(request, ticket_number)
    if forbidden:
        return forbidden
    if request.method == "POST":
        form = TicketManageForm(request.POST)
        if form.is_valid():
            update_ticket(ticket=ticket, actor=request.user, **form.cleaned_data)
            messages.success(request, "Ticket updated.")
        else:
            messages.error(request, "Ticket update was not valid.")
    return redirect("shit:detail", ticket_number=ticket.ticket_number)


@login_required
@require_POST
def ticket_asset_add(request, ticket_number):
    ticket, forbidden = _manage_ticket_or_forbidden(request, ticket_number)
    if forbidden:
        return forbidden

    form = TicketAssetLinkForm(request.POST, ticket=ticket)
    if form.is_valid():
        try:
            add_ticket_asset_link(
                ticket=ticket,
                actor=request.user,
                **form.cleaned_data,
            )
            messages.success(
                request,
                f"{form.cleaned_data['asset'].asset_id} linked to the ticket.",
            )
        except ValueError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "The asset relationship was not valid.")
    return redirect("shit:detail", ticket_number=ticket.ticket_number)


@login_required
@require_POST
def ticket_asset_update(request, ticket_number, link_id):
    ticket, forbidden = _manage_ticket_or_forbidden(request, ticket_number)
    if forbidden:
        return forbidden
    link = get_object_or_404(
        TicketAssetLink.objects.select_related("asset"),
        pk=link_id,
        ticket=ticket,
    )
    form = TicketAssetLinkEditForm(request.POST)
    if form.is_valid():
        try:
            update_ticket_asset_link(
                ticket=ticket,
                link=link,
                actor=request.user,
                **form.cleaned_data,
            )
            messages.success(request, f"{link.asset.asset_id} relationship updated.")
        except ValueError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "The asset relationship update was not valid.")
    return redirect("shit:detail", ticket_number=ticket.ticket_number)


@login_required
@require_POST
def ticket_asset_remove(request, ticket_number, link_id):
    ticket, forbidden = _manage_ticket_or_forbidden(request, ticket_number)
    if forbidden:
        return forbidden
    link = get_object_or_404(
        TicketAssetLink.objects.select_related("asset"),
        pk=link_id,
        ticket=ticket,
    )
    asset_id = link.asset.asset_id
    try:
        remove_ticket_asset_link(ticket=ticket, link=link, actor=request.user)
        messages.success(request, f"{asset_id} unlinked from the ticket.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("shit:detail", ticket_number=ticket.ticket_number)


@login_required
@require_POST
def ticket_board_move(request, ticket_number):
    ticket = get_object_or_404(
        Ticket.objects.select_related(
            "assigned_department",
            "assigned_user",
        ),
        ticket_number=ticket_number,
    )
    if not can_manage_ticket(request.user, ticket):
        if _is_ajax(request):
            return JsonResponse(
                {"ok": False, "error": "You may not manage this ticket."},
                status=403,
            )
        return HttpResponseForbidden(
            "You do not have permission to manage this ticket."
        )

    form = TicketBoardMoveForm(request.POST)
    if not form.is_valid():
        if _is_ajax(request):
            return JsonResponse(
                {"ok": False, "errors": form.errors.get_json_data()},
                status=400,
            )
        messages.error(request, "The requested board move was invalid.")
        return redirect("shit:list")

    target_status = form.cleaned_data["status"]
    before_ticket_number = form.cleaned_data["before_ticket_number"].strip().upper()

    # A client may only name a queue neighbor it can already see, and that
    # neighbor must actually belong to the target status. The service then
    # performs the authoritative transaction and ordering update.
    if before_ticket_number:
        neighbor = _visible_tickets(request.user).filter(
            ticket_number=before_ticket_number
        ).first()
        if neighbor is None or neighbor.status != target_status:
            if _is_ajax(request):
                return JsonResponse(
                    {"ok": False, "error": "Invalid queue neighbor."},
                    status=400,
                )
            messages.error(request, "That queue position is no longer available.")
            return redirect("shit:list")

    try:
        moved_ticket = move_ticket_on_board(
            ticket=ticket,
            actor=request.user,
            target_status=target_status,
            before_ticket_number=before_ticket_number,
            reorder=form.cleaned_data["reorder"],
            direction=form.cleaned_data["direction"],
        )
    except ValueError as exc:
        if _is_ajax(request):
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        messages.error(request, str(exc))
        return redirect("shit:list")

    if _is_ajax(request):
        return JsonResponse(
            {
                "ok": True,
                "ticket_number": moved_ticket.ticket_number,
                "status": moved_ticket.status,
                "status_display": moved_ticket.get_status_display(),
                "queue_position": moved_ticket.queue_position,
            }
        )

    params = {
        "view": "board",
        "scope": form.cleaned_data.get("scope") or "mine",
    }
    if form.cleaned_data.get("query"):
        params["q"] = form.cleaned_data["query"]
    messages.success(request, f"{moved_ticket.ticket_number} updated.")
    return redirect(f"{reverse('shit:list')}?{urlencode(params)}")


@login_required
def ticket_comment(request, ticket_number):
    ticket = get_object_or_404(Ticket, ticket_number=ticket_number)
    if not can_view_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have access to this ticket.")
    if request.method == "POST":
        form = TicketCommentForm(request.POST)
        if form.is_valid():
            visibility = form.cleaned_data["visibility"]
            if visibility == TicketComment.Visibility.INTERNAL and not can_manage_ticket(
                request.user,
                ticket,
            ):
                return HttpResponseForbidden(
                    "Only ticket agents may add internal notes."
                )
            add_comment(
                ticket=ticket,
                actor=request.user,
                body=form.cleaned_data["body"],
                visibility=visibility,
            )
    return redirect("shit:detail", ticket_number=ticket.ticket_number)


@login_required
def ticket_attachment(request, ticket_number):
    ticket = get_object_or_404(Ticket, ticket_number=ticket_number)
    if not can_view_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have access to this ticket.")
    if request.method == "POST":
        form = TicketAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            add_attachment(
                ticket=ticket,
                actor=request.user,
                uploaded_file=form.cleaned_data["file"],
            )
    return redirect("shit:detail", ticket_number=ticket.ticket_number)
