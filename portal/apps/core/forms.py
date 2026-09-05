from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class DesktopInitialAdminForm(forms.Form):
    username = forms.CharField(max_length=150)
    display_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username already exists.")
        return username

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")
        if password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned


class PortalBackupExportForm(forms.Form):
    include_media = forms.BooleanField(
        required=False,
        initial=True,
        label="Include uploaded files",
        help_text="Recommended for portable restores. Includes BAM evidence and SHIT attachments stored under the media directory.",
    )


class PortalBackupImportForm(forms.Form):
    backup = forms.FileField(
        label="B.S. Portal backup",
        help_text="Select a .bsbackup file exported by B.S. Portal.",
    )
    confirmation = forms.CharField(
        max_length=16,
        label="Type RESTORE to continue",
        help_text="The current database will be safety-backed up and then replaced.",
    )

    def clean_backup(self):
        upload = self.cleaned_data["backup"]
        if not upload.name.lower().endswith(".bsbackup"):
            raise forms.ValidationError("Select a B.S. Portal .bsbackup file.")
        return upload

    def clean_confirmation(self):
        value = self.cleaned_data["confirmation"].strip()
        if value != "RESTORE":
            raise forms.ValidationError("Type RESTORE exactly to confirm the replacement operation.")
        return value
