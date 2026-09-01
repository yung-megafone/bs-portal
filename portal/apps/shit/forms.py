from django import forms
from django.contrib.auth import get_user_model

from apps.bam.models import Asset
from apps.departments.models import Department

from .models import Ticket, TicketComment


def _asset_queryset():
    return Asset.objects.select_related(
        "department",
        "asset_type",
        "status",
        "current_custodian",
    ).all()


class AssetChoiceField(forms.ModelChoiceField):
    """BAM-backed asset selector with useful context in the option label."""

    def label_from_instance(self, asset):
        details = []
        hardware = " ".join(
            part for part in (asset.manufacturer, asset.model) if part
        ).strip()
        if hardware:
            details.append(hardware)
        details.extend(
            [
                asset.asset_type.code,
                asset.department.code,
                asset.status.name,
            ]
        )
        if asset.current_custodian:
            details.append(f"custodian: {asset.current_custodian}")
        return f"{asset.asset_id} — {' · '.join(details)}"


class TicketCreateForm(forms.Form):
    title = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 10}))
    ticket_type = forms.ChoiceField(choices=Ticket.Type.choices)
    severity = forms.ChoiceField(
        choices=Ticket.Severity.choices,
        initial=Ticket.Severity.SEV5,
    )
    assigned_department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        label="Route to department",
    )
    related_asset = AssetChoiceField(
        queryset=_asset_queryset(),
        required=False,
    )
    related_document = forms.CharField(
        max_length=120,
        required=False,
        help_text="Optional PSOP/document ID, e.g. STD-7100",
    )
    attachment = forms.FileField(required=False)


class TicketManageForm(forms.Form):
    status = forms.ChoiceField(choices=Ticket.Status.choices)
    severity = forms.ChoiceField(choices=Ticket.Severity.choices)
    assigned_department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
    )
    assigned_user = forms.ModelChoiceField(
        queryset=get_user_model().objects.filter(is_active=True),
        required=False,
    )
    related_asset = AssetChoiceField(
        queryset=_asset_queryset(),
        required=False,
    )
    related_document = forms.CharField(max_length=120, required=False)

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get("assigned_user")
        department = cleaned.get("assigned_department")
        if user and department and not user.is_staff:
            if not user.department_memberships.filter(
                department=department,
                is_active=True,
            ).exists():
                self.add_error(
                    "assigned_user",
                    "Assignee must be an active member of the assigned department.",
                )
        return cleaned


class TicketBoardMoveForm(forms.Form):
    status = forms.ChoiceField(choices=Ticket.Status.choices)
    before_ticket_number = forms.CharField(max_length=32, required=False)
    reorder = forms.BooleanField(required=False)
    direction = forms.ChoiceField(
        choices=[
            ("", "Keep current queue position"),
            ("up", "Move up"),
            ("down", "Move down"),
            ("top", "Move to top"),
            ("bottom", "Move to bottom"),
        ],
        required=False,
    )
    scope = forms.ChoiceField(
        choices=[
            ("mine", "My tickets"),
            ("department", "Department queue"),
            ("all", "All tickets"),
        ],
        required=False,
    )
    query = forms.CharField(max_length=200, required=False)


class TicketCommentForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Comment",
    )
    visibility = forms.ChoiceField(
        choices=TicketComment.Visibility.choices,
        initial=TicketComment.Visibility.PUBLIC,
    )


class TicketAttachmentForm(forms.Form):
    file = forms.FileField()
