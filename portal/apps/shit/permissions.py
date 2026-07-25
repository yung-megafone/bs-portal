def is_department_agent(user, department):
    if not user.is_authenticated or department is None:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return user.department_memberships.filter(department=department, is_active=True).exists()


def can_view_ticket(user, ticket):
    return bool(user.is_staff or user.is_superuser or ticket.requester_id == user.id or ticket.assigned_user_id == user.id or is_department_agent(user, ticket.assigned_department))


def can_manage_ticket(user, ticket):
    return bool(user.is_staff or user.is_superuser or ticket.assigned_user_id == user.id or is_department_agent(user, ticket.assigned_department))
