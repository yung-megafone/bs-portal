from django import forms
from django.contrib.auth import get_user_model

from apps.bam.models import Asset
from apps.departments.models import Department

from .models import Ticket, TicketComment


class TicketCreateForm(forms.Form):
    title = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 7}))
    ticket_type = forms.ChoiceField(choices=Ticket.Type.choices)
    severity = forms.ChoiceField(choices=Ticket.Severity.choices, initial=Ticket.Severity.SEV5)
    assigned_department = forms.ModelChoiceField(queryset=Department.objects.filter(is_active=True), required=False, label="Route to department")
    related_asset = forms.ModelChoiceField(queryset=Asset.objects.all(), required=False)
    related_document = forms.CharField(max_length=120, required=False, help_text="Optional PSOP/document ID, e.g. STD-7100")
    attachment = forms.FileField(required=False)


class TicketManageForm(forms.Form):
    status = forms.ChoiceField(choices=Ticket.Status.choices)
    severity = forms.ChoiceField(choices=Ticket.Severity.choices)
    assigned_department = forms.ModelChoiceField(queryset=Department.objects.filter(is_active=True), required=False)
    assigned_user = forms.ModelChoiceField(queryset=get_user_model().objects.filter(is_active=True), required=False)
    related_asset = forms.ModelChoiceField(queryset=Asset.objects.all(), required=False)
    related_document = forms.CharField(max_length=120, required=False)

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get("assigned_user")
        department = cleaned.get("assigned_department")
        if user and department and not user.is_staff:
            if not user.department_memberships.filter(department=department, is_active=True).exists():
                self.add_error("assigned_user", "Assignee must be an active member of the assigned department.")
        return cleaned


class TicketCommentForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), label="Comment")
    visibility = forms.ChoiceField(choices=TicketComment.Visibility.choices, initial=TicketComment.Visibility.PUBLIC)


class TicketAttachmentForm(forms.Form):
    file = forms.FileField()
