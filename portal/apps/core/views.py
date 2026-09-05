import os

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render

from apps.core.version import RELEASE_CHANNEL, __version__


def health(request):
    return JsonResponse({"status": "ok"})


def about(request):
    build_id = os.environ.get("BS_PORTAL_BUILD_ID", "").strip()
    return render(
        request,
        "core/about.html",
        {
            "portal_version": __version__,
            "release_channel": RELEASE_CHANNEL,
            "build_id": build_id,
        },
    )


def privacy(request):
    return render(request, "core/privacy.html")


def security(request):
    return render(request, "core/security.html")


def license_info(request):
    return render(request, "core/license.html")


@login_required
def dashboard(request):
    from apps.bam.models import Asset
    from apps.shit.models import Ticket
    from apps.timeclock.services import get_clock_state

    memberships = request.user.department_memberships.select_related("department")
    bam_summary = {
        "total": Asset.objects.count(),
        "in_custody": Asset.objects.filter(current_custodian__isnull=False).count(),
    }
    shit_summary = {
        "open": Ticket.objects.exclude(
            status__in=[Ticket.Status.CLOSED, Ticket.Status.CANCELLED]
        ).count(),
        "mine": Ticket.objects.filter(
            Q(requester=request.user) | Q(assigned_user=request.user)
        ).distinct().count(),
    }
    timeclock_summary = get_clock_state(request.user)
    return render(
        request,
        "core/dashboard.html",
        {
            "memberships": memberships,
            "bam_summary": bam_summary,
            "shit_summary": shit_summary,
            "timeclock_summary": timeclock_summary,
        },
    )
