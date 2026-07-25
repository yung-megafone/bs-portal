from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TicketAttachmentForm, TicketCommentForm, TicketCreateForm, TicketManageForm
from .models import Ticket, TicketComment
from .permissions import can_manage_ticket, can_view_ticket
from .services import add_attachment, add_comment, create_ticket, update_ticket


def _visible_tickets(user):
    qs = Ticket.objects.select_related("requester", "assigned_department", "assigned_user", "related_asset")
    if user.is_staff or user.is_superuser:
        return qs
    department_ids = user.department_memberships.filter(is_active=True).values_list("department_id", flat=True)
    return qs.filter(Q(requester=user) | Q(assigned_user=user) | Q(assigned_department_id__in=department_ids)).distinct()


@login_required
def ticket_list(request):
    scope = request.GET.get("scope", "mine")
    query = request.GET.get("q", "").strip()
    tickets = _visible_tickets(request.user)
    if scope == "mine":
        tickets = tickets.filter(Q(requester=request.user) | Q(assigned_user=request.user))
    elif scope == "department":
        department_ids = request.user.department_memberships.filter(is_active=True).values_list("department_id", flat=True)
        tickets = tickets.filter(assigned_department_id__in=department_ids)
    elif scope == "all" and not (request.user.is_staff or request.user.is_superuser):
        scope = "mine"
        tickets = tickets.filter(Q(requester=request.user) | Q(assigned_user=request.user))
    if query:
        tickets = tickets.filter(Q(ticket_number__icontains=query) | Q(title__icontains=query) | Q(description__icontains=query) | Q(related_document__icontains=query) | Q(related_asset__asset_id__icontains=query))
    return render(request, "shit/ticket_list.html", {"tickets": tickets[:500], "scope": scope, "query": query})


@login_required
def ticket_create(request):
    if request.method == "POST":
        form = TicketCreateForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = create_ticket(actor=request.user, **{k: form.cleaned_data[k] for k in ["title", "description", "ticket_type", "severity", "assigned_department", "related_asset", "related_document"]})
            if form.cleaned_data.get("attachment"):
                add_attachment(ticket=ticket, actor=request.user, uploaded_file=form.cleaned_data["attachment"])
            messages.success(request, f"{ticket.ticket_number} created.")
            return redirect("shit:detail", ticket_number=ticket.ticket_number)
    else:
        form = TicketCreateForm()
    return render(request, "shit/ticket_form.html", {"form": form})


@login_required
def ticket_detail(request, ticket_number):
    ticket = get_object_or_404(Ticket.objects.select_related("requester", "assigned_department", "assigned_user", "related_asset"), ticket_number=ticket_number)
    if not can_view_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have access to this ticket.")
    manage = can_manage_ticket(request.user, ticket)
    comments = ticket.comments.select_related("author")
    if not manage:
        comments = comments.filter(visibility=TicketComment.Visibility.PUBLIC)
    return render(request, "shit/ticket_detail.html", {
        "ticket": ticket, "can_manage": manage, "comments": comments,
        "events": ticket.events.select_related("actor")[:200] if manage else [],
        "attachments": ticket.attachments.select_related("uploaded_by")[:100],
        "comment_form": TicketCommentForm(), "attachment_form": TicketAttachmentForm(),
        "manage_form": TicketManageForm(initial={"status": ticket.status, "severity": ticket.severity, "assigned_department": ticket.assigned_department, "assigned_user": ticket.assigned_user, "related_asset": ticket.related_asset, "related_document": ticket.related_document}) if manage else None,
    })


@login_required
def ticket_manage(request, ticket_number):
    ticket = get_object_or_404(Ticket, ticket_number=ticket_number)
    if not can_manage_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have permission to manage this ticket.")
    if request.method == "POST":
        form = TicketManageForm(request.POST)
        if form.is_valid():
            update_ticket(ticket=ticket, actor=request.user, **form.cleaned_data)
            messages.success(request, "Ticket updated.")
    return redirect("shit:detail", ticket_number=ticket.ticket_number)


@login_required
def ticket_comment(request, ticket_number):
    ticket = get_object_or_404(Ticket, ticket_number=ticket_number)
    if not can_view_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have access to this ticket.")
    if request.method == "POST":
        form = TicketCommentForm(request.POST)
        if form.is_valid():
            visibility = form.cleaned_data["visibility"]
            if visibility == TicketComment.Visibility.INTERNAL and not can_manage_ticket(request.user, ticket):
                return HttpResponseForbidden("Only ticket agents may add internal notes.")
            add_comment(ticket=ticket, actor=request.user, body=form.cleaned_data["body"], visibility=visibility)
    return redirect("shit:detail", ticket_number=ticket.ticket_number)


@login_required
def ticket_attachment(request, ticket_number):
    ticket = get_object_or_404(Ticket, ticket_number=ticket_number)
    if not can_view_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have access to this ticket.")
    if request.method == "POST":
        form = TicketAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            add_attachment(ticket=ticket, actor=request.user, uploaded_file=form.cleaned_data["file"])
    return redirect("shit:detail", ticket_number=ticket.ticket_number)
