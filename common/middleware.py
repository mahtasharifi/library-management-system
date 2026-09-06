"""Cross-cutting HTTP middleware."""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import time

from django.conf import settings

from .request_context import request_id_var

security_logger = logging.getLogger("security")

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class CorrelationIdMiddleware:
    """Attach a bounded request correlation identifier to every response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _REQUEST_ID_PATTERN.fullmatch(incoming) else secrets.token_hex(16)
        token = request_id_var.set(request_id)
        request.request_id = request_id
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)


class ContentSecurityPolicyMiddleware:
    """Set security headers that are not covered by Django's built-ins."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        policy = getattr(settings, "CONTENT_SECURITY_POLICY", "")
        if policy:
            response.setdefault("Content-Security-Policy", policy)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response


class RequestMetricsMiddleware:
    """Record low-cardinality process metrics without retaining request data."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .metrics_state import record_request

        started = time.perf_counter()
        response = self.get_response(request)
        record_request(response.status_code, time.perf_counter() - started)
        return response


class AdminAuditMiddleware:
    """Record privileged state-changing requests without logging bodies or credentials."""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _is_admin_api(path: str) -> bool:
        return path.startswith("/api/admin/") or path.startswith("/library/api/admin/")

    @staticmethod
    def _actor_id(request) -> str:
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return "anonymous"
        digest = hashlib.sha256(str(user.pk).encode("utf-8")).hexdigest()
        return digest[:12]

    def __call__(self, request):
        response = self.get_response(request)
        if self._is_admin_api(request.path) and request.method not in self.SAFE_METHODS:
            security_logger.info(
                "admin_action",
                extra={
                    "event": "admin_action",
                    "actor": self._actor_id(request),
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                },
            )
        return response

class MfaEnforcementMiddleware:
    """Require a fresh MFA-verified session for protected authenticated users."""

    EXEMPT_PREFIXES = (
        "/static/",
        "/media/",
        "/health/",
        "/ready/",
        "/live/",
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/mfa/setup/",
        "/accounts/mfa/verify/",
        "/accounts/logout/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "MFA_ENFORCEMENT_ENABLED", True):
            return self.get_response(request)
        if request.path.startswith(self.EXEMPT_PREFIXES):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return self.get_response(request)

        from django.contrib.auth import logout
        from django.shortcuts import redirect
        from django.urls import reverse
        from apps.accounts import mfa

        if not mfa.is_mfa_required(user):
            return self.get_response(request)

        credential = mfa.get_credential(user)
        verified_user = request.session.get("mfa_verified_user_id")
        verified_version = request.session.get("mfa_version")
        if credential.is_enabled and verified_user == user.pk and verified_version == credential.version:
            return self.get_response(request)

        user_id = user.pk
        target = request.get_full_path()
        logout(request)
        request.session["mfa_pending_user_id"] = user_id
        request.session["mfa_pending_remember"] = True
        request.session["mfa_pending_next"] = target if target.startswith("/") and not target.startswith("//") else "/library/"
        request.session.set_expiry(10 * 60)
        security_logger.warning("mfa_session_required", extra={"event": "auth.mfa_required"})
        return redirect(reverse("accounts:mfa_verify") if credential.is_enabled else reverse("accounts:mfa_setup"))
