import hashlib
import mimetypes
import secrets
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Ticket, TicketAttachment, TicketComment, TicketEvent


TICKET_SUFFIX_BYTES = 3
TICKET_NUMBER_MAX_ATTEMPTS = 32


def _event(ticket, actor, event_type, summary, metadata=None):
    return TicketEvent.objects.create(
        ticket=ticket,
        actor=actor,
        event_type=event_type,
        summary=summary,
        metadata=metadata or {},
    )


def _generate_ticket_number():
    """
    Generate the preferred human-readable SHIT ticket identifier.

    Format:
        SHIT-YY-HHHHHH

    HHHHHH is a six-character uppercase hexadecimal suffix. The complete
    ticket number remains protected by Ticket.ticket_number's UNIQUE
    constraint; generation does not rely on probability alone for uniqueness.
    """
    year = date.today().year % 100
    suffix = secrets.token_hex(TICKET_SUFFIX_BYTES).upper()
    return f"SHIT-{year:02d}-{suffix}"


def create_ticket(
    *,
    actor,
    title,
    description,
    ticket_type,
    severity,
    assigned_department=None,
    related_asset=None,
    related_document="",
):
    """
    Create a ticket with an immutable, automatically-generated ticket number.

    A database uniqueness collision is retried with a new random suffix. The
    nested atomic block creates a savepoint so an IntegrityError does not poison
    the outer transaction.
    """
    for _ in range(TICKET_NUMBER_MAX_ATTEMPTS):
        ticket_number = _generate_ticket_number()

        try:
            with transaction.atomic():
                ticket = Ticket.objects.create(
                    ticket_number=ticket_number,
                    title=title.strip(),
                    description=description.strip(),
                    ticket_type=ticket_type,
                    severity=severity,
                    requester=actor,
                    assigned_department=assigned_department,
                    related_asset=related_asset,
                    related_document=(related_document or "").strip().upper(),
                )

                _event(
                    ticket,
                    actor,
                    TicketEvent.EventType.CREATED,
                    f"Ticket created as {ticket.ticket_number}.",
                    {
                        "ticket_number": ticket.ticket_number,
                        "severity": severity,
                        "type": ticket_type,
                        "department": (
                            assigned_department.code
                            if assigned_department
                            else None
                        ),
                    },
                )
                return ticket
        except IntegrityError:
            # ticket_number is UNIQUE. A generated collision is harmless:
            # consume neither identifier nor ticket and retry with a new suffix.
            #
            # Other integrity errors should be extraordinarily unlikely here
            # because form/service validation resolves required relationships
            # before creation. If all attempts fail, surface a clear error.
            continue

    raise RuntimeError(
        "Unable to allocate a unique SHIT ticket number after "
        f"{TICKET_NUMBER_MAX_ATTEMPTS} attempts."
    )


def update_ticket(
    *,
    ticket,
    actor,
    status,
    severity,
    assigned_department,
    assigned_user,
    related_asset,
    related_document,
):
    before = {
        "status": ticket.status,
        "severity": ticket.severity,
        "department": (
            ticket.assigned_department.code
            if ticket.assigned_department
            else None
        ),
        "assignee": str(ticket.assigned_user_id) if ticket.assigned_user_id else None,
        "asset": ticket.related_asset.asset_id if ticket.related_asset else None,
        "document": ticket.related_document,
    }

    with transaction.atomic():
        ticket.status = status
        ticket.severity = severity
        ticket.assigned_department = assigned_department
        ticket.assigned_user = assigned_user
        ticket.related_asset = related_asset
        ticket.related_document = (related_document or "").strip().upper()

        now = timezone.now()
        if status == Ticket.Status.RESOLVED and not ticket.resolved_at:
            ticket.resolved_at = now
        elif status not in {Ticket.Status.RESOLVED, Ticket.Status.CLOSED}:
            ticket.resolved_at = None

        if status == Ticket.Status.CLOSED and not ticket.closed_at:
            ticket.closed_at = now
        elif status != Ticket.Status.CLOSED:
            ticket.closed_at = None

        ticket.save()

        after = {
            "status": ticket.status,
            "severity": ticket.severity,
            "department": (
                ticket.assigned_department.code
                if ticket.assigned_department
                else None
            ),
            "assignee": str(ticket.assigned_user_id) if ticket.assigned_user_id else None,
            "asset": ticket.related_asset.asset_id if ticket.related_asset else None,
            "document": ticket.related_document,
        }

        event_map = [
            ("status", TicketEvent.EventType.STATUS_CHANGED, "Status"),
            ("severity", TicketEvent.EventType.SEVERITY_CHANGED, "Severity"),
            ("department", TicketEvent.EventType.DEPARTMENT_CHANGED, "Department"),
            ("assignee", TicketEvent.EventType.ASSIGNEE_CHANGED, "Assignee"),
            ("asset", TicketEvent.EventType.ASSET_LINKED, "Related asset"),
            ("document", TicketEvent.EventType.DOCUMENT_LINKED, "Related document"),
        ]

        for key, event_type, label in event_map:
            if before[key] != after[key]:
                _event(
                    ticket,
                    actor,
                    event_type,
                    f"{label} changed from {before[key] or '—'} "
                    f"to {after[key] or '—'}.",
                    {"from": before[key], "to": after[key]},
                )

    return ticket


def add_comment(
    *,
    ticket,
    actor,
    body,
    visibility=TicketComment.Visibility.PUBLIC,
):
    with transaction.atomic():
        comment = TicketComment.objects.create(
            ticket=ticket,
            author=actor,
            body=body.strip(),
            visibility=visibility,
        )
        event_type = (
            TicketEvent.EventType.INTERNAL_NOTE
            if visibility == TicketComment.Visibility.INTERNAL
            else TicketEvent.EventType.COMMENTED
        )
        _event(
            ticket,
            actor,
            event_type,
            "Internal note added."
            if visibility == TicketComment.Visibility.INTERNAL
            else "Comment added.",
        )
    return comment


def add_attachment(*, ticket, actor, uploaded_file):
    digest = hashlib.sha256()

    for chunk in uploaded_file.chunks():
        digest.update(chunk)

    uploaded_file.seek(0)

    mime_type = (
        getattr(uploaded_file, "content_type", "")
        or mimetypes.guess_type(uploaded_file.name)[0]
        or ""
    )

    attachment = TicketAttachment.objects.create(
        ticket=ticket,
        uploaded_by=actor,
        file=uploaded_file,
        original_filename=uploaded_file.name,
        mime_type=mime_type,
        size_bytes=getattr(uploaded_file, "size", 0),
        sha256=digest.hexdigest(),
    )

    _event(
        ticket,
        actor,
        TicketEvent.EventType.ATTACHMENT_ADDED,
        f"Attachment added: {attachment.original_filename}.",
    )
    return attachment
