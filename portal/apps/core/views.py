import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render

from apps.core.forms import DesktopInitialAdminForm
from apps.core.version import RELEASE_CHANNEL, __version__



def desktop_setup(request):
    if not getattr(settings, "DESKTOP_MODE", False):
        raise Http404

    remote_addr = request.META.get("REMOTE_ADDR", "")
    if remote_addr not in {"127.0.0.1", "::1"}:
        raise PermissionDenied

    User = get_user_model()
    if User.objects.exists():
        return redirect("login")

    form = DesktopInitialAdminForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.create_superuser(
            username=form.cleaned_data["username"],
            email=form.cleaned_data.get("email", ""),
            password=form.cleaned_data["password1"],
        )
        display_name = form.cleaned_data.get("display_name", "").strip()
        if hasattr(user, "display_name") and display_name:
            user.display_name = display_name
            user.save(update_fields=["display_name"])
        login(request, user)
        messages.success(request, "Initial administrator created. B.S. Portal is ready.")
        return redirect("dashboard")

    return render(request, "core/desktop_setup.html", {"form": form})

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
    from apps.bam.models import Asset, AssetCheckout, AssetRequest
    from apps.shit.models import Ticket
    from apps.timeclock.services import get_clock_state

    memberships = request.user.department_memberships.select_related("department")
    bam_summary = {
        "total": Asset.objects.count(),
        "active_checkouts": AssetCheckout.objects.filter(returned_at__isnull=True).count(),
        "my_checkouts": AssetCheckout.objects.filter(custodian=request.user, returned_at__isnull=True).count(),
        "my_open_requests": AssetRequest.objects.filter(requester=request.user).exclude(
            status__in=[AssetRequest.Status.CANCELLED, AssetRequest.Status.DENIED, AssetRequest.Status.COMPLETED]
        ).count(),
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
