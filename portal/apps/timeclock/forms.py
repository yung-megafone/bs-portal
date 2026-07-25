from django import forms

from .models import Punch


class PunchCorrectionForm(forms.Form):
    corrected_punch_type = forms.ChoiceField(
        choices=Punch.PunchType.choices,
        label="Corrected punch type",
    )
    corrected_occurred_at = forms.DateTimeField(
        label="Corrected timestamp",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
    )
    reason = forms.CharField(
        label="Reason",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Required. The original punch remains preserved.",
    )
