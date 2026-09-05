from django import forms
from django.contrib.auth import get_user_model

from .models import Asset, AssetEvidence, AssetStatus, AssetType


class AssetCreateForm(forms.ModelForm):
    preferred_suffix = forms.CharField(
        required=False,
        max_length=4,
        label="Preferred suffix",
        help_text=(
            "Optional four-character hexadecimal preference (for example 6969). "
            "If that suffix is already used in this department/type namespace, BAM will assign a random suffix instead."
        ),
        widget=forms.TextInput(attrs={"placeholder": "6969", "maxlength": "4", "autocomplete": "off"}),
    )
    status = forms.ModelChoiceField(queryset=AssetStatus.objects.filter(is_active=True))
    custodian = forms.ModelChoiceField(
        queryset=get_user_model().objects.all(),
        required=False,
        help_text="Leave blank to use BAM's default stock custodian (Vanguard when configured).",
    )
    asset_photo = forms.FileField(required=False)
    serial_evidence = forms.FileField(required=False)

    class Meta:
        model = Asset
        fields = [
            "department",
            "asset_type",
            "status",
            "ownership",
            "manufacturer",
            "model",
            "serial_number",
            "custodian",
            "acquired_at",
            "notes",
        ]
        widgets = {"acquired_at": forms.DateInput(attrs={"type": "date"})}

    def clean_preferred_suffix(self):
        value = (self.cleaned_data.get("preferred_suffix") or "").strip().upper()
        if not value:
            return ""
        if len(value) != 4 or any(ch not in "0123456789ABCDEF" for ch in value):
            raise forms.ValidationError("Enter exactly four hexadecimal characters (0-9, A-F).")
        return value


class AssetEditForm(forms.Form):
    ownership = forms.ChoiceField(choices=Asset.Ownership.choices)
    manufacturer = forms.CharField(max_length=120, required=False)
    model = forms.CharField(max_length=160, required=False)
    serial_number = forms.CharField(max_length=200, required=False)
    acquired_at = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(required=False, widget=forms.Textarea)
    automatic_allocation_enabled = forms.BooleanField(
        required=False,
        label="Allow automatic allocation",
        help_text="Managers may still allocate this asset manually when automation is disabled.",
    )
    allocation_hold = forms.BooleanField(
        required=False,
        label="Allocation hold",
        help_text="Hard hold: exclude this asset from both automatic and normal availability matching.",
    )
    allocation_hold_reason = forms.CharField(max_length=240, required=False)


class AssetStatusForm(forms.Form):
    status = forms.ModelChoiceField(queryset=AssetStatus.objects.filter(is_active=True))
    reason = forms.CharField(max_length=240, required=False)


class CustodyForm(forms.Form):
    custodian = forms.ModelChoiceField(queryset=get_user_model().objects.all(), required=False)
    reason = forms.CharField(max_length=240, required=False)


class AssetEvidenceForm(forms.Form):
    kind = forms.ChoiceField(choices=AssetEvidence.Kind.choices)
    file = forms.FileField()
    notes = forms.CharField(max_length=240, required=False)


class AssetChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        hardware = " ".join(part for part in [obj.manufacturer, obj.model] if part).strip()
        label = obj.asset_id
        if hardware:
            label += f" — {hardware}"
        label += f" · {obj.status.name}"
        if obj.current_custodian:
            label += f" · custodian {obj.current_custodian}"
        return label


class AssetRequestCreateForm(forms.Form):
    purpose = forms.CharField(
        max_length=200,
        help_text="Project or purpose this equipment will support.",
    )
    related_ticket = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Related SHIT ticket",
        help_text="Optional operational work this asset request supports.",
    )
    priority = forms.ChoiceField(
        choices=(),
        help_text="BAM request priority is separate from SHIT severity and does not automatically jump the waitlist.",
    )
    requested_start = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    requested_end = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    desired_completion_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional project completion target; this is not the reservation end date.",
    )
    justification = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 5}))

    department = forms.ModelChoiceField(queryset=None)
    asset_type = forms.ModelChoiceField(queryset=None, label="Asset type / class")
    preference_mode = forms.ChoiceField(
        choices=(),
        widget=forms.RadioSelect,
        label="Allocation preference",
    )
    preferred_asset = AssetChoiceField(
        queryset=None,
        required=False,
        help_text="Required for preferred/exact modes. The asset may be unavailable now; exact mode will wait for it.",
    )
    item_note = forms.CharField(
        max_length=240,
        required=False,
        label="Requirement note",
        help_text="Optional requirement-specific context, e.g. discrete GPU preferred.",
    )

    def __init__(self, *args, user=None, asset=None, related_ticket=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.departments.models import Department
        from apps.shit.models import Ticket
        from apps.shit.permissions import filter_visible_tickets
        from .models import Asset, AssetRequest, AssetRequestItem, AssetType

        self.fields["department"].queryset = Department.objects.filter(is_active=True).order_by("code")
        self.fields["asset_type"].queryset = AssetType.objects.filter(is_active=True).order_by("code")
        self.fields["preferred_asset"].queryset = (
            Asset.objects.filter(status__is_terminal=False)
            .select_related("department", "asset_type", "status", "current_custodian")
            .order_by("asset_id")
        )
        self.fields["priority"].choices = AssetRequest.Priority.choices
        self.fields["preference_mode"].choices = AssetRequestItem.PreferenceMode.choices
        self.fields["related_ticket"].queryset = (
            filter_visible_tickets(Ticket.objects.all(), user).order_by("-updated_at")
            if user and user.is_authenticated
            else Ticket.objects.none()
        )

        if asset is not None:
            self.initial.update({
                "department": asset.department_id,
                "asset_type": asset.asset_type_id,
                "preferred_asset": asset.pk,
                "preference_mode": AssetRequestItem.PreferenceMode.PREFER,
            })
        else:
            self.initial.setdefault("preference_mode", AssetRequestItem.PreferenceMode.ANY)
        self.initial.setdefault("priority", AssetRequest.Priority.NORMAL)
        if related_ticket is not None:
            self.initial["related_ticket"] = related_ticket.pk

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("requested_start")
        end = cleaned.get("requested_end")
        if start and end and end < start:
            self.add_error("requested_end", "Requested end date cannot be before the start date.")
        desired = cleaned.get("desired_completion_date")
        if start and desired and desired < start:
            self.add_error("desired_completion_date", "Desired completion date cannot be before the requested start date.")

        mode = cleaned.get("preference_mode")
        preferred = cleaned.get("preferred_asset")
        department = cleaned.get("department")
        asset_type = cleaned.get("asset_type")
        from .models import AssetRequestItem
        if mode in {AssetRequestItem.PreferenceMode.PREFER, AssetRequestItem.PreferenceMode.REQUIRE} and not preferred:
            self.add_error("preferred_asset", "Select the asset you prefer or require.")
        if preferred and department and preferred.department_id != department.pk:
            self.add_error("preferred_asset", "Preferred asset must belong to the selected department.")
        if preferred and asset_type and preferred.asset_type_id != asset_type.pk:
            self.add_error("preferred_asset", "Preferred asset must match the selected asset type.")
        if mode == AssetRequestItem.PreferenceMode.ANY:
            cleaned["preferred_asset"] = None
        return cleaned


class AssetRequestItemForm(forms.Form):
    department = forms.ModelChoiceField(queryset=None)
    asset_type = forms.ModelChoiceField(queryset=None, label="Asset type / class")
    preference_mode = forms.ChoiceField(choices=(), widget=forms.RadioSelect)
    preferred_asset = AssetChoiceField(queryset=None, required=False)
    note = forms.CharField(max_length=240, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.departments.models import Department
        from .models import Asset, AssetRequestItem, AssetType
        self.fields["department"].queryset = Department.objects.filter(is_active=True).order_by("code")
        self.fields["asset_type"].queryset = AssetType.objects.filter(is_active=True).order_by("code")
        self.fields["preference_mode"].choices = AssetRequestItem.PreferenceMode.choices
        self.fields["preferred_asset"].queryset = (
            Asset.objects.filter(status__is_terminal=False)
            .select_related("department", "asset_type", "status", "current_custodian")
            .order_by("asset_id")
        )
        self.initial.setdefault("preference_mode", AssetRequestItem.PreferenceMode.ANY)

    def clean(self):
        cleaned = super().clean()
        from .models import AssetRequestItem
        mode = cleaned.get("preference_mode")
        preferred = cleaned.get("preferred_asset")
        department = cleaned.get("department")
        asset_type = cleaned.get("asset_type")
        if mode in {AssetRequestItem.PreferenceMode.PREFER, AssetRequestItem.PreferenceMode.REQUIRE} and not preferred:
            self.add_error("preferred_asset", "Select the asset you prefer or require.")
        if preferred and department and preferred.department_id != department.pk:
            self.add_error("preferred_asset", "Preferred asset must belong to the selected department.")
        if preferred and asset_type and preferred.asset_type_id != asset_type.pk:
            self.add_error("preferred_asset", "Preferred asset must match the selected asset type.")
        if mode == AssetRequestItem.PreferenceMode.ANY:
            cleaned["preferred_asset"] = None
        return cleaned


class AssetAllocationForm(forms.Form):
    allocated_asset = AssetChoiceField(
        queryset=None,
        required=False,
        label="Reserve asset",
        help_text="Leave blank to let BAM follow the requester's preference and choose an eligible equivalent.",
    )

    def __init__(self, *args, item=None, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Asset
        if item is None:
            self.fields["allocated_asset"].queryset = Asset.objects.none()
        else:
            # Only offer assets that are actually eligible for this request
            # window. The service still re-validates availability inside the
            # transaction, so form filtering is convenience rather than trust.
            from .services import eligible_assets_for_item
            self.fields["allocated_asset"].queryset = eligible_assets_for_item(item, respect_automation_policy=False)


class AssetRequestActionForm(forms.Form):
    reason = forms.CharField(max_length=240, required=False)

class AssetCheckoutActionForm(forms.Form):
    reason = forms.CharField(max_length=240, required=False)


class AssetHandoffChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return (
            f"{obj.request.request_number} — {obj.request.requester} · "
            f"{obj.request.requested_start} → {obj.request.requested_end}"
        )


class AssetHandoffForm(forms.Form):
    next_item = AssetHandoffChoiceField(queryset=None, label="Hand off to")
    reason = forms.CharField(max_length=240, required=False)

    def __init__(self, *args, checkout=None, **kwargs):
        super().__init__(*args, **kwargs)
        if checkout is None:
            from .models import AssetRequestItem
            self.fields["next_item"].queryset = AssetRequestItem.objects.none()
        else:
            from .services import handoff_candidates_for_checkout
            self.fields["next_item"].queryset = handoff_candidates_for_checkout(checkout)



class AssetSelfReleaseForm(forms.Form):
    condition = forms.ChoiceField(
        choices=(),
        label="Asset condition",
        help_text="Anything other than Good places the asset on allocation hold instead of passing it to the next requester.",
    )
    notes = forms.CharField(
        max_length=240,
        required=False,
        label="Release notes",
        widget=forms.TextInput(attrs={"placeholder": "Optional condition/accessory notes"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import AssetCheckout
        self.fields["condition"].choices = AssetCheckout.ReturnCondition.choices
        self.initial.setdefault("condition", AssetCheckout.ReturnCondition.GOOD)
