"""Reusable security helpers with no business-domain dependencies."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import F
from django.utils import timezone

from .models import RateLimitBucket

security_logger = logging.getLogger("security")


def get_client_ip(request) -> str | None:
    """Return a client address without trusting proxy headers by default."""
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR")


def hash_identifier(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int = 0


def _window_start(window_seconds: int):
    now = timezone.now()
    epoch = int(now.timestamp())
    started = epoch - (epoch % window_seconds)
    return datetime.fromtimestamp(started, tz=timezone.get_current_timezone())


def check_rate_limit(namespace: str, identifier: str, *, limit: int, window_seconds: int) -> RateLimitResult:
    """Shared fixed-window limiter; database failure fails closed on abuse-sensitive paths."""
    identifier_hash = hash_identifier(identifier)
    window_started_at = _window_start(window_seconds)
    try:
        with transaction.atomic():
            # get_or_create handles a concurrent unique-key insert with its own
            # savepoint. Re-lock an existing row before the read/modify/write.
            bucket, created = RateLimitBucket.objects.get_or_create(
                namespace=namespace,
                identifier_hash=identifier_hash,
                window_started_at=window_started_at,
                defaults={"count": 1},
            )
            if created:
                return RateLimitResult(True)
            bucket = RateLimitBucket.objects.select_for_update().get(pk=bucket.pk)
            if bucket.count >= limit:
                elapsed = int((timezone.now() - window_started_at).total_seconds())
                return RateLimitResult(False, max(window_seconds - elapsed, 1))
            RateLimitBucket.objects.filter(pk=bucket.pk).update(count=F("count") + 1)
            return RateLimitResult(True)
    except DatabaseError:
        security_logger.error("rate_limit_backend_unavailable", extra={"event": "rate_limit_backend_unavailable"})
        return RateLimitResult(False, min(window_seconds, 60))


def purge_expired_rate_limits(*, older_than_seconds: int = 86400) -> int:
    cutoff = timezone.now() - timedelta(seconds=older_than_seconds)
    count, _ = RateLimitBucket.objects.filter(window_started_at__lt=cutoff).delete()
    return count
