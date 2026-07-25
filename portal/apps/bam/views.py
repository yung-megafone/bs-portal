from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AssetCreateForm, AssetEditForm, AssetEvidenceForm, AssetStatusForm, CustodyForm
from .models import Asset, AssetEvidence, AssetStatus, AssetType
from .services import add_evidence, assign_custody, change_asset_status, create_asset, update_asset_details


@login_required
def asset_list(request):
    query = request.GET.get("q", "").strip()
    assets = Asset.objects.select_related("department", "asset_type", "status", "current_custodian")
    if query:
        assets = assets.filter(
            Q(asset_id__icontains=query)
            | Q(manufacturer__icontains=query)
            | Q(model__icontains=query)
            | Q(serial_number__icontains=query)
            | Q(notes__icontains=query)
        )
    context = {
        "assets": assets[:500],
        "query": query,
        "total_count": Asset.objects.count(),
        "types_count": AssetType.objects.filter(is_active=True).count(),
        "statuses": AssetStatus.objects.filter(is_active=True),
    }
    return render(request, "bam/asset_list.html", context)


@login_required
def asset_create(request):
    if request.method == "POST":
        form = AssetCreateForm(request.POST, request.FILES)
        if form.is_valid():
            asset = create_asset(
                actor=request.user,
                department=form.cleaned_data["department"],
                asset_type=form.cleaned_data["asset_type"],
                status=form.cleaned_data["status"],
                ownership=form.cleaned_data["ownership"],
                manufacturer=form.cleaned_data["manufacturer"],
                model=form.cleaned_data["model"],
                serial_number=form.cleaned_data["serial_number"],
                custodian=form.cleaned_data["custodian"],
                acquired_at=form.cleaned_data["acquired_at"],
                notes=form.cleaned_data["notes"],
                preferred_suffix=form.cleaned_data.get("preferred_suffix"),
            )
            if form.cleaned_data.get("asset_photo"):
                add_evidence(
                    asset=asset,
                    uploaded_file=form.cleaned_data["asset_photo"],
                    kind=AssetEvidence.Kind.ASSET_PHOTO,
                    actor=request.user,
                )
            if form.cleaned_data.get("serial_evidence"):
                add_evidence(
                    asset=asset,
                    uploaded_file=form.cleaned_data["serial_evidence"],
                    kind=AssetEvidence.Kind.SERIAL,
                    actor=request.user,
                )
            requested = form.cleaned_data.get("preferred_suffix")
            if requested and asset.unique_hex != requested:
                messages.warning(request, f"Preferred suffix {requested} was unavailable; BAM assigned {asset.unique_hex} instead.")
            elif requested:
                messages.success(request, f"Preferred suffix {asset.unique_hex} assigned.")
            return redirect("bam:detail", asset_id=asset.asset_id)
    else:
        form = AssetCreateForm()
    return render(request, "bam/asset_form.html", {"form": form})


@login_required
def asset_detail(request, asset_id):
    asset = get_object_or_404(
        Asset.objects.select_related("department", "asset_type", "status", "current_custodian", "created_by"),
        asset_id=asset_id,
    )
    return render(
        request,
        "bam/asset_detail.html",
        {
            "asset": asset,
            "events": asset.events.select_related("actor")[:100],
            "evidence": asset.evidence.select_related("uploaded_by")[:100],
            "custody": asset.custody_history.select_related("custodian", "assigned_by")[:100],
            "status_form": AssetStatusForm(initial={"status": asset.status}),
            "evidence_form": AssetEvidenceForm(),
            "custody_form": CustodyForm(initial={"custodian": asset.current_custodian}),
        },
    )


@login_required
def asset_status(request, asset_id):
    asset = get_object_or_404(Asset.objects.select_related("status"), asset_id=asset_id)
    if request.method == "POST":
        form = AssetStatusForm(request.POST)
        if form.is_valid():
            change_asset_status(
                asset=asset,
                new_status=form.cleaned_data["status"],
                actor=request.user,
                reason=form.cleaned_data["reason"],
            )
    return redirect("bam:detail", asset_id=asset.asset_id)


@login_required
def evidence_add(request, asset_id):
    asset = get_object_or_404(Asset, asset_id=asset_id)
    if request.method == "POST":
        form = AssetEvidenceForm(request.POST, request.FILES)
        if form.is_valid():
            add_evidence(
                asset=asset,
                uploaded_file=form.cleaned_data["file"],
                kind=form.cleaned_data["kind"],
                actor=request.user,
                notes=form.cleaned_data["notes"],
            )
    return redirect("bam:detail", asset_id=asset.asset_id)


@login_required
def asset_edit(request, asset_id):
    asset = get_object_or_404(Asset, asset_id=asset_id)
    initial = {
        "ownership": asset.ownership,
        "manufacturer": asset.manufacturer,
        "model": asset.model,
        "serial_number": asset.serial_number,
        "acquired_at": asset.acquired_at,
        "notes": asset.notes,
    }
    if request.method == "POST":
        form = AssetEditForm(request.POST)
        if form.is_valid():
            update_asset_details(asset=asset, actor=request.user, **form.cleaned_data)
            return redirect("bam:detail", asset_id=asset.asset_id)
    else:
        form = AssetEditForm(initial=initial)
    return render(request, "bam/asset_edit.html", {"asset": asset, "form": form})


@login_required
def asset_custody(request, asset_id):
    asset = get_object_or_404(Asset, asset_id=asset_id)
    if request.method == "POST":
        form = CustodyForm(request.POST)
        if form.is_valid():
            assign_custody(asset=asset, custodian=form.cleaned_data["custodian"], actor=request.user, reason=form.cleaned_data["reason"])
    return redirect("bam:detail", asset_id=asset.asset_id)
