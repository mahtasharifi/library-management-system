"""Protected operational metrics with no user-level labels or payload data."""

from __future__ import annotations

import secrets
import time
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils import timezone

from .metrics_state import snapshot


def _authorized(request) -> bool:
    user = getattr(request, "user", None)
    if getattr(user, "is_staff", False) and getattr(user, "is_authenticated", False):
        return True
    expected = getattr(settings, "METRICS_TOKEN", "")
    supplied = request.headers.get("Authorization", "")
    if not expected or not supplied.startswith("Bearer "):
        return False
    return secrets.compare_digest(supplied[7:], expected)


@require_GET
def metrics(request):
    if not _authorized(request):
        return JsonResponse({"detail": "not found"}, status=404)

    from apps.books.models import BackgroundJob, TaskWorkerHeartbeat

    started = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    database_latency_ms = round((time.perf_counter() - started) * 1000, 3)
    max_age = timedelta(seconds=getattr(settings, "BACKGROUND_WORKER_MAX_AGE_SECONDS", 120))
    worker_cutoff = timezone.now() - max_age
    payload = snapshot()
    payload.update(
        {
            "database_latency_ms": database_latency_ms,
            "background_queue_depth": BackgroundJob.objects.filter(status=BackgroundJob.STATUS_QUEUED).count(),
            "background_failed_jobs": BackgroundJob.objects.filter(status=BackgroundJob.STATUS_FAILED).count(),
            "background_worker_available": TaskWorkerHeartbeat.objects.filter(seen_at__gte=worker_cutoff).exists(),
        }
    )
    return JsonResponse(payload)
