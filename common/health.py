"""Health, readiness, and liveness probes."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET


def _database_is_ready() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except Exception:
        return False


def _cache_is_ready() -> bool:
    try:
        key = "healthcheck:cache:v1"
        cache.set(key, "ok", timeout=5)
        return cache.get(key) == "ok"
    except Exception:
        return False


def _storage_is_ready() -> bool:
    """Check storage readiness without mutating the filesystem on a GET probe."""
    try:
        root = Path(settings.MEDIA_ROOT)
        return root.exists() and root.is_dir() and os.access(root, os.W_OK)
    except OSError:
        return False


def _worker_is_ready() -> bool:
    if getattr(settings, "BACKGROUND_JOBS_EAGER", False):
        return True
    try:
        from apps.books.models import TaskWorkerHeartbeat

        cutoff = timezone.now() - timedelta(seconds=getattr(settings, "BACKGROUND_WORKER_MAX_AGE_SECONDS", 120))
        return TaskWorkerHeartbeat.objects.filter(seen_at__gte=cutoff).exists()
    except Exception:
        return False


@require_GET
def live(request):
    return JsonResponse({"status": "ok"})


@require_GET
def ready(request):
    checks = {
        "database": _database_is_ready(),
        "cache": _cache_is_ready(),
        "storage": _storage_is_ready(),
        "worker": _worker_is_ready(),
    }
    is_ready = all(checks.values())
    payload = {"status": "ok" if is_ready else "unavailable"}
    if getattr(settings, "HEALTH_CHECK_DETAILS", False):
        payload["checks"] = checks
    return JsonResponse(payload, status=200 if is_ready else 503)


@require_GET
def health(request):
    return ready(request)
