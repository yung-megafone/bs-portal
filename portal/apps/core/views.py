from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import Q


def health(request):
    return JsonResponse({"status": "ok"})


@login_required
def dashboard(request):
    from apps.bam.models import Asset
    from apps.shit.models import Ticket

    memberships = request.user.department_memberships.select_related("department")
    bam_summary = {
        "total": Asset.objects.count(),
        "in_custody": Asset.objects.filter(current_custodian__isnull=False).count(),
    }
    shit_summary = {
        "open": Ticket.objects.exclude(status__in=[Ticket.Status.CLOSED, Ticket.Status.CANCELLED]).count(),
        "mine": Ticket.objects.filter(Q(requester=request.user) | Q(assigned_user=request.user)).distinct().count(),
    }
    return render(request, "core/dashboard.html", {"memberships": memberships, "bam_summary": bam_summary, "shit_summary": shit_summary})
