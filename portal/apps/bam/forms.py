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
    custodian = forms.ModelChoiceField(queryset=get_user_model().objects.all(), required=False)
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
