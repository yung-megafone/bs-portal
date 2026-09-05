from django import forms
from django.contrib.auth import get_user_model

from apps.bam.models import Asset
from apps.departments.models import Department

from .models import Ticket, TicketAssetLink, TicketComment


def _asset_queryset():
    return Asset.objects.select_related(
        "department",
        "asset_type",
        "status",
        "current_custodian",
    ).all()


def _asset_label(asset):
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


class AssetChoiceField(forms.ModelChoiceField):
    """BAM-backed single-asset selector with useful context in the label."""

    def label_from_instance(self, asset):
        return _asset_label(asset)


class AssetMultipleChoiceField(forms.ModelMultipleChoiceField):
    """BAM-backed multi-asset selector using the same contextual labels."""

    def label_from_instance(self, asset):
        return _asset_label(asset)


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
    related_assets = AssetMultipleChoiceField(
        queryset=_asset_queryset(),
        required=False,
        label="Related assets",
        widget=forms.SelectMultiple(attrs={"size": 7}),
        help_text=(
            "Select one or more existing BAM assets. The initial relationship "
            "below is applied to every selected asset and can be refined later."
        ),
    )
    asset_relationship = forms.ChoiceField(
        choices=TicketAssetLink.RelationshipType.choices,
        initial=TicketAssetLink.RelationshipType.RELATED,
        label="Initial asset relationship",
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


class TicketAssetLinkForm(forms.Form):
    asset = AssetChoiceField(
        queryset=_asset_queryset(),
        label="BAM asset",
    )
    relationship_type = forms.ChoiceField(
        choices=TicketAssetLink.RelationshipType.choices,
        initial=TicketAssetLink.RelationshipType.RELATED,
        label="Relationship",
    )
    note = forms.CharField(
        max_length=240,
        required=False,
        label="Relationship note",
        help_text="Optional context about how this asset relates to the ticket.",
    )

    def __init__(self, *args, ticket=None, **kwargs):
        super().__init__(*args, **kwargs)
        if ticket is not None:
            self.fields["asset"].queryset = _asset_queryset().exclude(
                ticket_links__ticket=ticket
            )


class TicketAssetLinkEditForm(forms.Form):
    relationship_type = forms.ChoiceField(
        choices=TicketAssetLink.RelationshipType.choices,
        label="Relationship",
    )
    note = forms.CharField(
        max_length=240,
        required=False,
        label="Relationship note",
    )


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
