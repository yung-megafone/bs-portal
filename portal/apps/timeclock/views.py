from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PunchCorrectionForm
from .models import Punch
from .services import clock_in, clock_out, correct_punch, get_clock_state


@login_required
def timeclock_home(request):
    punches = (
        Punch.objects.filter(employee=request.user)
        .select_related("recorded_by")
        .prefetch_related("corrections__corrected_by")
        .order_by("-occurred_at", "-created_at")[:50]
    )
    state = get_clock_state(request.user)
    return render(
        request,
        "timeclock/timeclock_home.html",
        {"punches": punches, "clock_state": state},
    )


@login_required
def punch_action(request):
    if request.method != "POST":
        raise Http404

    action = request.POST.get("action")
    try:
        if action == "in":
            punch = clock_in(employee=request.user, actor=request.user)
            messages.success(
                request,
                f"Clocked in at {punch.occurred_at:%Y-%m-%d %H:%M:%S}.",
            )
        elif action == "out":
            punch = clock_out(employee=request.user, actor=request.user)
            messages.success(
                request,
                f"Clocked out at {punch.occurred_at:%Y-%m-%d %H:%M:%S}.",
            )
        else:
            messages.error(request, "Invalid timeclock action.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))

    return redirect("timeclock:home")


@login_required
def correct_punch_view(request, punch_id):
    if not request.user.is_staff:
        raise PermissionDenied

    punch = get_object_or_404(
        Punch.objects.select_related("employee", "recorded_by").prefetch_related(
            "corrections__corrected_by"
        ),
        pk=punch_id,
    )

    initial = {
        "corrected_punch_type": punch.effective_punch_type,
        "corrected_occurred_at": punch.effective_occurred_at,
    }

    if request.method == "POST":
        form = PunchCorrectionForm(request.POST)
        if form.is_valid():
            try:
                correct_punch(
                    punch=punch,
                    actor=request.user,
                    corrected_punch_type=form.cleaned_data["corrected_punch_type"],
                    corrected_occurred_at=form.cleaned_data["corrected_occurred_at"],
                    reason=form.cleaned_data["reason"],
                )
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(
                    request,
                    f"Correction recorded for {punch.employee}. Original punch preserved.",
                )
                return redirect("timeclock:home")
    else:
        form = PunchCorrectionForm(initial=initial)

    return render(
        request,
        "timeclock/punch_correction.html",
        {"punch": punch, "form": form},
    )
