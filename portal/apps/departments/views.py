from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Department


@login_required
def department_list(request):
    departments = Department.objects.prefetch_related("memberships").all()
    return render(request, "departments/list.html", {"departments": departments})
