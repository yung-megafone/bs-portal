from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render


def health(request):
    return JsonResponse({"status": "ok"})


@login_required
def dashboard(request):
    from apps.bam.models import Asset

    memberships = request.user.department_memberships.select_related("department")
    bam_summary = {
        "total": Asset.objects.count(),
        "in_custody": Asset.objects.filter(current_custodian__isnull=False).count(),
    }
    return render(request, "core/dashboard.html", {"memberships": memberships, "bam_summary": bam_summary})
