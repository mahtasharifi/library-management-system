"""HTTP views for authentication, MFA, profile management, and notifications."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from common.security import check_rate_limit, get_client_ip, hash_identifier
from common.i18n import translate as t
from . import mfa, repositories, services
from .forms import (
    LoginForm,
    MfaCodeForm,
    MfaRecoveryRegenerateForm,
    MfaSetupForm,
    PasswordChangeForm,
    SignUpForm,
    UserProfileForm,
)

security_logger = logging.getLogger("security")

MFA_PENDING_USER_KEY = "mfa_pending_user_id"
MFA_PENDING_REMEMBER_KEY = "mfa_pending_remember"
MFA_PENDING_NEXT_KEY = "mfa_pending_next"
MFA_VERIFIED_USER_KEY = "mfa_verified_user_id"
MFA_VERSION_KEY = "mfa_version"
MFA_RECOVERY_DISPLAY_KEY = "mfa_recovery_codes_once"


def _safe_next(request, candidate: str | None) -> str:
    if (
        candidate
        and candidate != "/"
        and url_has_allowed_host_and_scheme(
            candidate,
            {request.get_host()},
            request.is_secure(),
        )
    ):
        return candidate

    return settings.LOGIN_REDIRECT_URL

def _start_mfa_pending(request, user, *, remember_me: bool, next_url: str | None = None) -> None:
    """Store only the minimum first-factor state in a fresh anonymous session."""
    request.session.flush()
    request.session[MFA_PENDING_USER_KEY] = user.pk
    request.session[MFA_PENDING_REMEMBER_KEY] = bool(remember_me)
    request.session[MFA_PENDING_NEXT_KEY] = _safe_next(request, next_url)
    request.session.set_expiry(10 * 60)


def _pending_user(request):
    user_id = request.session.get(MFA_PENDING_USER_KEY)
    if not user_id:
        return None
    return User.objects.filter(pk=user_id, is_active=True).first()


def _clear_pending(request) -> None:
    for key in (MFA_PENDING_USER_KEY, MFA_PENDING_REMEMBER_KEY, MFA_PENDING_NEXT_KEY):
        request.session.pop(key, None)


def _complete_mfa_login(request, user) -> str:
    remember_me = bool(request.session.get(MFA_PENDING_REMEMBER_KEY))
    next_url = _safe_next(request, request.session.get(MFA_PENDING_NEXT_KEY))
    _clear_pending(request)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    credential = mfa.get_credential(user)
    request.session[MFA_VERIFIED_USER_KEY] = user.pk
    request.session[MFA_VERSION_KEY] = credential.version
    if not remember_me:
        request.session.set_expiry(0)
    return next_url


class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST":
            identifier = f"{get_client_ip(request) or '-'}:{request.POST.get('username', '')}"
            result = check_rate_limit("login", identifier, limit=10, window_seconds=300)
            if not result.allowed:
                security_logger.warning("login_rate_limited", extra={"event": "auth.rate_limited"})
                return render(request, self.template_name, {"form": self.get_form(), "rate_limited": True}, status=429)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        remember_me = bool(form.cleaned_data.get("remember_me"))
        if (
            getattr(settings, "MFA_ENFORCEMENT_ENABLED", True)
            and mfa.is_mfa_required(user)
        ):
            _start_mfa_pending(
                self.request,
                user,
                remember_me=remember_me,
                next_url=self.get_redirect_url(),
            )
            credential = mfa.get_credential(user)

            security_logger.info(
                "mfa_challenge_started",
                extra={"event": "auth.mfa_challenge"},
            )

            return redirect(
                "accounts:mfa_verify"
                if credential.is_enabled
                else "accounts:mfa_setup"
            )
        if not remember_me:
            self.request.session.set_expiry(0)
        response = super().form_valid(form)
        security_logger.info("authentication_succeeded", extra={"event": "auth.login_success"})
        return response

    def form_invalid(self, form):
        identifier = hash_identifier(self.request.POST.get("username", ""))
        security_logger.warning(
            "authentication_failed",
            extra={"event": "auth.login_failure", "subject_hash": identifier},
        )
        return super().form_invalid(form)

    def get_success_url(self):
        return _safe_next(self.request, self.get_redirect_url())


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")
    http_method_names = ["post", "options"]


def mfa_setup_view(request):
    if not getattr(settings, "MFA_ENFORCEMENT_ENABLED", False):
        return redirect("accounts:profile" if request.user.is_authenticated else "accounts:login")
    user = request.user if request.user.is_authenticated else _pending_user(request)
    if not user or not mfa.is_mfa_required(user):
        return redirect("accounts:login")

    credential = mfa.get_credential(user)
    if credential.is_enabled:
        return redirect("accounts:mfa_verify" if not request.user.is_authenticated else "accounts:profile")

    secret = mfa.pending_secret(user)
    if not secret:
        credential, secret = mfa.start_enrollment(user)

    form = MfaSetupForm(request.POST or None)
    if request.method == "POST":
        identifier = f"{get_client_ip(request) or '-'}:{user.pk}"
        limit = check_rate_limit("mfa_setup", identifier, limit=8, window_seconds=300)
        if not limit.allowed:
            security_logger.warning("mfa_setup_rate_limited", extra={"event": "auth.mfa_rate_limited"})
            return render(request, "accounts/mfa_setup.html", _mfa_setup_context(user, secret, form, True), status=429)
        if form.is_valid():
            recovery_codes = mfa.enable_enrollment(user, form.cleaned_data["code"])
            if recovery_codes:
                security_logger.info("mfa_enrolled", extra={"event": "auth.mfa_enrolled"})
                if not request.user.is_authenticated:
                    _complete_mfa_login(request, user)
                else:
                    credential.refresh_from_db()
                    request.session[MFA_VERIFIED_USER_KEY] = user.pk
                    request.session[MFA_VERSION_KEY] = credential.version
                request.session[MFA_RECOVERY_DISPLAY_KEY] = recovery_codes
                return redirect("accounts:mfa_recovery_codes")
            form.add_error("code", t("accounts.messages.mfa_setup_invalid"))
    return render(request, "accounts/mfa_setup.html", _mfa_setup_context(user, secret, form, False))


def _mfa_setup_context(user, secret, form, rate_limited: bool) -> dict:
    return {
        "form": form,
        "qr_data_uri": mfa.qr_data_uri(user, secret),
        "manual_secret": secret,
        "rate_limited": rate_limited,
    }


def mfa_verify_view(request):
    if not getattr(settings, "MFA_ENFORCEMENT_ENABLED", False):
        return redirect("accounts:profile" if request.user.is_authenticated else "accounts:login")
    user = _pending_user(request)
    if not user:
        return redirect("accounts:login")
    credential = mfa.get_credential(user)
    if not credential.is_enabled:
        return redirect("accounts:mfa_setup")

    form = MfaCodeForm(request.POST or None)
    if request.method == "POST":
        identifier = f"{get_client_ip(request) or '-'}:{user.pk}"
        limit = check_rate_limit("mfa_verify", identifier, limit=8, window_seconds=300)
        if not limit.allowed:
            security_logger.warning("mfa_verify_rate_limited", extra={"event": "auth.mfa_rate_limited"})
            return render(request, "accounts/mfa_verify.html", {"form": form, "rate_limited": True}, status=429)
        if form.is_valid():
            result = mfa.verify_second_factor(user, form.cleaned_data["code"])
            if result.accepted:
                next_url = _complete_mfa_login(request, user)
                security_logger.info(
                    "mfa_succeeded",
                    extra={"event": "auth.mfa_success", "recovery": result.used_recovery_code},
                )
                if result.used_recovery_code:
                    messages.warning(request, t("accounts.messages.recovery_code_used"))
                return redirect(next_url)
            security_logger.warning("mfa_failed", extra={"event": "auth.mfa_failure"})
            form.add_error("code", t("accounts.messages.mfa_invalid_or_replayed"))
    return render(request, "accounts/mfa_verify.html", {"form": form})


@login_required
def mfa_security_view(request):
    """Compatibility redirect: the dedicated account-security UI was removed."""
    return redirect("accounts:profile")


@login_required
@require_POST
def mfa_rotate_view(request):
    if not getattr(settings, "MFA_ENFORCEMENT_ENABLED", False):
        return redirect("accounts:profile" if request.user.is_authenticated else "accounts:login")
    form = MfaRecoveryRegenerateForm(request.POST, user=request.user)
    if not form.is_valid():
        messages.error(request, t("accounts.messages.mfa_rotation_credentials_required"))
        return redirect("accounts:profile")
    result = mfa.verify_second_factor(request.user, form.cleaned_data["code"])
    if not result.accepted:
        messages.error(request, t("accounts.validation.mfa_code_invalid"))
        return redirect("accounts:profile")
    mfa.reset_mfa(request.user)
    mfa.start_enrollment(request.user)
    security_logger.info("mfa_rotation_started", extra={"event": "auth.mfa_rotation"})
    return redirect("accounts:mfa_setup")


@login_required
def mfa_recovery_codes_view(request):
    if not getattr(settings, "MFA_ENFORCEMENT_ENABLED", False):
        return redirect("accounts:profile" if request.user.is_authenticated else "accounts:login")
    codes = request.session.pop(MFA_RECOVERY_DISPLAY_KEY, None)
    if not codes:
        return redirect("accounts:profile")
    return render(request, "accounts/mfa_recovery_codes.html", services.account_context(request.user, recovery_codes=codes))


def signup_view(request):
    if request.method == "POST":
        result = check_rate_limit("signup", get_client_ip(request) or "unknown", limit=6, window_seconds=600)
        if not result.allowed:
            return render(request, "accounts/signup.html", {"form": SignUpForm(), "rate_limited": True}, status=429)
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            security_logger.info("account_created", extra={"event": "auth.signup_success"})
            if (
                getattr(settings, "MFA_ENFORCEMENT_ENABLED", True)
                and mfa.is_mfa_required(user)
            ):
                _start_mfa_pending(request, user, remember_me=True)
                return redirect("accounts:mfa_setup")
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, t("accounts.messages.signup_success"))
            return redirect("index")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def profile_view(request):
    return render(request, "accounts/profile.html", services.profile_context(request.user))


@login_required
def notifications_recent_view(request):
    items = repositories.recent_notifications(request.user, limit=5)
    payload = [services.notification_payload(item) for item in items]
    return JsonResponse({
        "success": True,
        "unread_count": repositories.notification_count(request.user, unread_only=True),
        "items": payload,
    })


@login_required
def notifications_view(request):
    active_filter = request.GET.get("filter", "all")
    if active_filter not in {"all", "unread"}:
        active_filter = "all"
    queryset = repositories.notification_queryset(request.user, unread_only=active_filter == "unread")
    context = services.account_context(
        request.user,
        notifications=queryset[:100],
        active_filter=active_filter,
        total_notifications=repositories.notification_count(request.user),
    )
    return render(request, "accounts/notifications.html", context)


@login_required
@require_POST
def notifications_read_view(request):
    request.user.library_notifications.filter(is_read=False).update(is_read=True)
    return redirect("accounts:notifications")


@login_required
@require_POST
def notification_read_view(request, notification_id):
    notification = get_object_or_404(request.user.library_notifications, id=notification_id)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return redirect("accounts:notifications")


@login_required
def profile_edit_view(request):
    profile = repositories.get_or_create_profile(request.user)
    form = UserProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, t("accounts.messages.profile_updated"))
        return redirect("accounts:profile")
    return render(request, "accounts/profile_edit.html", services.account_context(request.user, form=form))


@login_required
def change_password_view(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        request.session.cycle_key()
        security_logger.info("password_changed", extra={"event": "auth.password_change"})
        messages.success(request, t("accounts.messages.password_changed"))
        return redirect("accounts:profile")
    return render(request, "accounts/change_password.html", services.account_context(request.user, form=form))
