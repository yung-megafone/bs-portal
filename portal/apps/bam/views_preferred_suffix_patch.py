from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import AssetRegistrationForm
from .services import register_asset_with_preference


@login_required
def asset_register(request):
    if request.method == "POST":
        form = AssetRegistrationForm(request.POST)
        if form.is_valid():
            unsaved = form.save(commit=False)
            result = register_asset_with_preference(
                preferred_suffix=form.cleaned_data.get("preferred_suffix"),
                actor=request.user,
                department=unsaved.department,
                asset_type=unsaved.asset_type,
                ownership=unsaved.ownership,
                manufacturer=unsaved.manufacturer,
                model=unsaved.model,
                serial_number=unsaved.serial_number,
                acquired_at=unsaved.acquired_at,
                notes=unsaved.notes,
                registered_by=request.user,
            )

            if result.requested_suffix and not result.preferred_suffix_used:
                messages.warning(
                    request,
                    (
                        f"Preferred suffix {result.requested_suffix} was already in use. "
                        f"BAM assigned {result.assigned_suffix} instead."
                    ),
                )
            elif result.preferred_suffix_used:
                messages.success(
                    request,
                    f"Preferred suffix {result.assigned_suffix} was available and assigned.",
                )
            else:
                messages.success(
                    request,
                    f"Asset registered with generated suffix {result.assigned_suffix}.",
                )

            return redirect("bam:asset_detail", pk=result.asset.pk)
    else:
        form = AssetRegistrationForm()

    return render(request, "bam/asset_register.html", {"form": form})
