from apps.departments.models import DepartmentMembership


MANAGER_ROLES = [DepartmentMembership.Role.MANAGER, DepartmentMembership.Role.ADMIN]


def managed_department_ids(user):
    if not user.is_authenticated:
        return []
    if user.is_staff or user.is_superuser:
        return None
    return user.department_memberships.filter(
        is_active=True,
        role__in=MANAGER_ROLES,
    ).values_list("department_id", flat=True)


def can_manage_asset_request_department(user, department):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return user.department_memberships.filter(
        department=department,
        is_active=True,
        role__in=MANAGER_ROLES,
    ).exists()


def can_manage_asset_request(user, asset_request):
    """Whole-request authority requires authority over every requested department."""
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    request_departments = set(asset_request.items.values_list("department_id", flat=True))
    if not request_departments:
        return False
    user_departments = set(
        user.department_memberships.filter(
            is_active=True,
            role__in=MANAGER_ROLES,
        ).values_list("department_id", flat=True)
    )
    return request_departments.issubset(user_departments)


def can_view_asset_request(user, asset_request):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser or asset_request.requester_id == user.id:
        return True
    request_departments = asset_request.items.values_list("department_id", flat=True)
    return user.department_memberships.filter(
        department_id__in=request_departments,
        is_active=True,
        role__in=MANAGER_ROLES,
    ).exists()
