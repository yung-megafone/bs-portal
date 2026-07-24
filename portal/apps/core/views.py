from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render


def health(request):
    return JsonResponse({"status": "ok"})


@login_required
def dashboard(request):
    memberships = request.user.department_memberships.select_related("department")
    return render(request, "core/dashboard.html", {"memberships": memberships})
