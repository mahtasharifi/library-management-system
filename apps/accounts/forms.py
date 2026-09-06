"""Validated forms for authentication and profile management."""

from __future__ import annotations

from pathlib import Path
import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm as DjangoPasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from .models import UserProfile
from common.i18n import translate as t

PHONE_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")
ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp", "image/avif"}
ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024


def _validate_unique_email(email: str, *, exclude_user_id: int | None = None) -> str:
    queryset = User.objects.filter(email__iexact=email)
    if exclude_user_id:
        queryset = queryset.exclude(pk=exclude_user_id)
    if queryset.exists():
        raise forms.ValidationError(t("accounts.validation.email_exists"))
    return email


def _validate_phone(value: str) -> str:
    value = value.strip().replace(" ", "").replace("-", "")
    if value and not PHONE_PATTERN.fullmatch(value):
        raise forms.ValidationError(t("accounts.validation.phone_invalid"))
    return value


def _read_upload_signature(uploaded, size: int = 32) -> bytes:
    position = uploaded.tell()
    uploaded.seek(0)
    signature = uploaded.read(size)
    uploaded.seek(position)
    return signature


def _avatar_signature_matches(extension: str, signature: bytes) -> bool:
    if extension in {".jpg", ".jpeg"}:
        return signature.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return signature.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp":
        return signature.startswith(b"RIFF") and signature[8:12] == b"WEBP"
    if extension == ".avif":
        return len(signature) >= 12 and signature[4:8] == b"ftyp" and b"avif" in signature[8:24]
    return False


def _validate_avatar(uploaded):
    if not uploaded:
        return uploaded
    if uploaded.size <= 0 or uploaded.size > MAX_AVATAR_SIZE:
        raise forms.ValidationError(t("accounts.validation.avatar_size"))
    extension = Path(uploaded.name).suffix.lower()
    content_type = (getattr(uploaded, "content_type", "") or "").lower()
    if extension not in ALLOWED_AVATAR_EXTENSIONS or content_type not in ALLOWED_AVATAR_TYPES:
        raise forms.ValidationError(t("accounts.validation.avatar_format"))
    if not _avatar_signature_matches(extension, _read_upload_signature(uploaded)):
        raise forms.ValidationError(t("accounts.validation.avatar_signature"))
    return uploaded


class SignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, required=True, label=t("common.labels.email"))
    first_name = forms.CharField(max_length=100, required=True, label=t("common.labels.name"))
    last_name = forms.CharField(max_length=100, required=True, label=t("common.labels.last_name"))
    phone_number = forms.CharField(max_length=15, required=True, label=t("common.labels.phone"))

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "phone_number", "password1", "password2")

    def clean_email(self):
        return _validate_unique_email(self.cleaned_data["email"].strip().lower())

    def clean_phone_number(self):
        return _validate_phone(self.cleaned_data["phone_number"])

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        if not commit:
            return user
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.phone_number = self.cleaned_data["phone_number"]
        profile.save(update_fields=["phone_number"])
        return user


class LoginForm(AuthenticationForm):
    remember_me = forms.BooleanField(required=False, initial=True)


class MfaCodeForm(forms.Form):
    code = forms.CharField(
        max_length=20,
        min_length=6,
        label=t("accounts.labels.mfa_or_recovery_code"),
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "spellcheck": "false"}),
    )

    def clean_code(self):
        value = self.cleaned_data["code"].strip().upper()
        compact = "".join(ch for ch in value if ch.isalnum())
        if (len(value) == 6 and value.isdigit()) or len(compact) == 12:
            return value
        raise forms.ValidationError(t("accounts.validation.mfa_code_invalid"))


class MfaSetupForm(forms.Form):
    code = forms.RegexField(
        regex=r"^[0-9]{6}$",
        max_length=6,
        min_length=6,
        label=t("accounts.labels.authenticator_code"),
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code"}),
    )


class MfaRecoveryRegenerateForm(forms.Form):
    current_password = forms.CharField(
        max_length=128,
        label=t("accounts.labels.current_password"),
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    code = forms.CharField(
        max_length=20,
        min_length=6,
        label=t("accounts.labels.mfa_code"),
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        value = self.cleaned_data["current_password"]
        if not self.user or not self.user.check_password(value):
            raise forms.ValidationError(t("accounts.validation.current_password_invalid"))
        return value


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, required=False, label=t("common.labels.name"))
    last_name = forms.CharField(max_length=100, required=False, label=t("common.labels.last_name"))
    email = forms.EmailField(required=True, label=t("common.labels.email"))
    phone_number = forms.CharField(max_length=15, required=False, label=t("common.labels.phone"))

    class Meta:
        model = UserProfile
        fields = ["phone_number", "avatar"]
        labels = {"avatar": t("accounts.labels.profile_avatar")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

    def clean_email(self):
        return _validate_unique_email(self.cleaned_data["email"].strip().lower(), exclude_user_id=self.instance.user_id)

    def clean_phone_number(self):
        return _validate_phone(self.cleaned_data.get("phone_number", ""))

    def clean_avatar(self):
        return _validate_avatar(self.cleaned_data.get("avatar"))

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=False)
        if not commit:
            return profile
        user = profile.user
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.email = self.cleaned_data["email"]
        user.save(update_fields=["first_name", "last_name", "email"])
        profile.save()
        return profile


class PasswordChangeForm(DjangoPasswordChangeForm):
    old_password = forms.CharField(label=t("accounts.labels.current_password"), widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
    new_password1 = forms.CharField(label=t("accounts.labels.new_password"), widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    new_password2 = forms.CharField(label=t("accounts.labels.new_password_repeat"), widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
