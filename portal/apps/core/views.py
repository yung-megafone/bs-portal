import os
from pathlib import Path
import tempfile


from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render

from apps.core.forms import DesktopInitialAdminForm, PortalBackupExportForm, PortalBackupImportForm
from apps.core.version import RELEASE_CHANNEL, __version__
from apps.core.database_backups import (
    DatabaseBackupError,
    create_portable_backup,
    list_saved_backups,
    restore_portable_backup,
    saved_backup_path,
)



def _write_uploaded_backup(upload) -> Path:
    temp_path = None
    with tempfile.NamedTemporaryFile(prefix="bsportal-upload-", suffix=".bsbackup", delete=False) as temp:
        temp_path = Path(temp.name)
        for chunk in upload.chunks():
            temp.write(chunk)
    return temp_path


def desktop_setup(request):
    if not getattr(settings, "DESKTOP_MODE", False):
        raise Http404

    remote_addr = request.META.get("REMOTE_ADDR", "")
    if remote_addr not in {"127.0.0.1", "::1"}:
        raise PermissionDenied

    User = get_user_model()
    if User.objects.exists():
        return redirect("login")

    action = request.POST.get("action", "create_admin") if request.method == "POST" else ""
    admin_form = DesktopInitialAdminForm(request.POST if action != "restore" else None)
    restore_form = PortalBackupImportForm(
        request.POST if action == "restore" else None,
        request.FILES if action == "restore" else None,
        prefix="restore",
    )

    if request.method == "POST" and action == "restore" and restore_form.is_valid():
        temp_path = None
        try:
            temp_path = _write_uploaded_backup(restore_form.cleaned_data["backup"])
            safety_backup, manifest = restore_portable_backup(temp_path)
        except DatabaseBackupError as exc:
            restore_form.add_error(None, f"Restore failed: {exc}")
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

        if not restore_form.errors:
            return render(
                request,
                "core/restore_complete.html",
                {
                    "source_version": manifest.get("portal_version", "unknown"),
                    "safety_backup": safety_backup.name,
                },
            )

    if request.method == "POST" and action != "restore" and admin_form.is_valid():
        user = User.objects.create_superuser(
            username=admin_form.cleaned_data["username"],
            email=admin_form.cleaned_data.get("email", ""),
            password=admin_form.cleaned_data["password1"],
        )
        display_name = admin_form.cleaned_data.get("display_name", "").strip()
        if hasattr(user, "display_name") and display_name:
            user.display_name = display_name
            user.save(update_fields=["display_name"])
        login(request, user)
        messages.success(request, "Initial administrator created. B.S. Portal is ready.")
        return redirect("dashboard")

    return render(
        request,
        "core/desktop_setup.html",
        {"form": admin_form, "restore_form": restore_form},
    )

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


def _require_superuser(request):
    if not request.user.is_superuser:
        raise PermissionDenied


@login_required
def data_management(request):
    _require_superuser(request)
    return render(
        request,
        "core/data_management.html",
        {
            "export_form": PortalBackupExportForm(initial={"include_media": True}),
            "import_form": PortalBackupImportForm(),
            "saved_backups": list_saved_backups(),
            "database_name": settings.DATABASES["default"].get("NAME", ""),
            "media_root": settings.MEDIA_ROOT,
            "desktop_mode": bool(getattr(settings, "DESKTOP_MODE", False)),
        },
    )


@login_required
def export_portal_backup(request):
    _require_superuser(request)
    if request.method != "POST":
        return redirect("data_management")

    form = PortalBackupExportForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Backup options were invalid.")
        return redirect("data_management")

    try:
        path = create_portable_backup(include_media=form.cleaned_data["include_media"])
    except DatabaseBackupError as exc:
        messages.error(request, f"Backup failed: {exc}")
        return redirect("data_management")

    response = FileResponse(path.open("rb"), as_attachment=True, filename=path.name)
    response["X-BS-Portal-Backup"] = "portable"
    return response


@login_required
def download_saved_backup(request, filename):
    _require_superuser(request)
    try:
        path = saved_backup_path(filename)
    except DatabaseBackupError as exc:
        raise Http404(str(exc)) from exc
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)


@login_required
def import_portal_backup(request):
    _require_superuser(request)
    if request.method != "POST":
        return redirect("data_management")

    form = PortalBackupImportForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(
            request,
            "core/data_management.html",
            {
                "export_form": PortalBackupExportForm(initial={"include_media": True}),
                "import_form": form,
                "saved_backups": list_saved_backups(),
                "database_name": settings.DATABASES["default"].get("NAME", ""),
                "media_root": settings.MEDIA_ROOT,
                "desktop_mode": bool(getattr(settings, "DESKTOP_MODE", False)),
            },
            status=400,
        )

    upload = form.cleaned_data["backup"]
    temp_path = None
    try:
        temp_path = _write_uploaded_backup(upload)
        safety_backup, manifest = restore_portable_backup(temp_path)
    except DatabaseBackupError as exc:
        messages.error(request, f"Restore failed: {exc}")
        return redirect("data_management")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    # Do not use Django messages or the normal base template after this point:
    # importing a database can legitimately replace the session/user rows that
    # authenticated the request. A standalone completion page is safe whether
    # the browser's old session survives or not.
    return render(
        request,
        "core/restore_complete.html",
        {
            "source_version": manifest.get("portal_version", "unknown"),
            "safety_backup": safety_backup.name,
        },
    )


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
