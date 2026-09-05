from django.db.models import Q


def is_department_agent(user, department):
    if not user.is_authenticated or department is None:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return user.department_memberships.filter(
        department=department,
        is_active=True,
    ).exists()


def filter_visible_tickets(queryset, user):
    """Apply SHIT's ticket-visibility boundary to an arbitrary Ticket queryset."""
    if user.is_staff or user.is_superuser:
        return queryset
    department_ids = user.department_memberships.filter(is_active=True).values_list(
        "department_id",
        flat=True,
    )
    return queryset.filter(
        Q(requester=user)
        | Q(assigned_user=user)
        | Q(assigned_department_id__in=department_ids)
    ).distinct()


def can_view_ticket(user, ticket):
    return bool(
        user.is_staff
        or user.is_superuser
        or ticket.requester_id == user.id
        or ticket.assigned_user_id == user.id
        or is_department_agent(user, ticket.assigned_department)
    )


def can_manage_ticket(user, ticket):
    return bool(
        user.is_staff
        or user.is_superuser
        or ticket.assigned_user_id == user.id
        or is_department_agent(user, ticket.assigned_department)
    )
