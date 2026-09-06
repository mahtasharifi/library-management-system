"""Durable background-job queue backed by the transactional application database."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from ..models import BackgroundJob

logger = logging.getLogger("security")

_RETRY_BASE_SECONDS = 30
_RETRY_MAX_SECONDS = 3600


def enqueue_job(job_type: str, payload: dict, *, created_by=None, max_attempts: int = 5) -> BackgroundJob:
    """Persist a job and optionally execute it eagerly outside Production."""
    job = BackgroundJob.objects.create(
        job_type=job_type,
        payload=payload,
        created_by=created_by if getattr(created_by, "is_authenticated", False) else None,
        max_attempts=max_attempts,
    )
    if getattr(settings, "BACKGROUND_JOBS_EAGER", False):
        process_job(job.pk)
        job.refresh_from_db()
    return job


def _lock_queryset():
    queryset = BackgroundJob.objects.filter(
        status=BackgroundJob.STATUS_QUEUED,
        available_at__lte=timezone.now(),
    ).order_by("available_at", "created_at")
    if connection.features.has_select_for_update:
        return queryset.select_for_update(skip_locked=connection.features.has_select_for_update_skip_locked)
    return queryset



def recover_stale_jobs() -> int:
    """Recover jobs left running after a worker crash or forced restart."""
    timeout_seconds = max(int(getattr(settings, "BACKGROUND_JOB_LOCK_TIMEOUT_SECONDS", 3600)), 60)
    cutoff = timezone.now() - timedelta(seconds=timeout_seconds)
    recovered = 0
    with transaction.atomic():
        stale_jobs = list(
            BackgroundJob.objects.select_for_update().filter(
                status=BackgroundJob.STATUS_RUNNING,
                locked_at__lt=cutoff,
            )
        )
        for job in stale_jobs:
            if job.attempts >= job.max_attempts:
                job.status = BackgroundJob.STATUS_FAILED
                job.completed_at = timezone.now()
                job.payload = {}
                job.last_error_code = "worker_timeout"
            else:
                job.status = BackgroundJob.STATUS_QUEUED
                job.available_at = timezone.now()
                job.last_error_code = "worker_timeout_retry"
            job.locked_at = None
            job.save(
                update_fields=[
                    "status", "available_at", "locked_at", "completed_at",
                    "payload", "last_error_code", "updated_at",
                ]
            )
            recovered += 1
    if recovered:
        logger.warning(
            "background_jobs_recovered",
            extra={"event": "background_jobs_recovered", "count": recovered},
        )
    return recovered

def claim_next_job() -> BackgroundJob | None:
    """Atomically claim one available job for this worker process."""
    with transaction.atomic():
        job = _lock_queryset().first()
        if job is None:
            return None
        job.status = BackgroundJob.STATUS_RUNNING
        job.attempts += 1
        job.locked_at = timezone.now()
        job.save(update_fields=["status", "attempts", "locked_at", "updated_at"])
        return job


def process_next_job() -> bool:
    job = claim_next_job()
    if job is None:
        return False
    process_job(job.pk, already_claimed=True)
    return True


def process_job(job_id: int, *, already_claimed: bool = False) -> None:
    """Execute one job and apply bounded exponential retry semantics."""
    job = BackgroundJob.objects.get(pk=job_id)
    if not already_claimed:
        with transaction.atomic():
            locked = BackgroundJob.objects.select_for_update().get(pk=job_id)
            if locked.status == BackgroundJob.STATUS_COMPLETED:
                return
            if locked.status == BackgroundJob.STATUS_FAILED and locked.attempts >= locked.max_attempts:
                return
            locked.status = BackgroundJob.STATUS_RUNNING
            locked.attempts += 1
            locked.locked_at = timezone.now()
            locked.save(update_fields=["status", "attempts", "locked_at", "updated_at"])
        job.refresh_from_db()

    try:
        result = _dispatch(job.job_type, job.payload)
    except Exception as exc:  # worker boundary; public error data is intentionally generic
        _record_failure(job.pk, exc)
        return
    _record_success(job.pk, result)


def _dispatch(job_type: str, payload: dict) -> dict:
    if job_type == BackgroundJob.TYPE_EMAIL:
        from .email import deliver_library_email

        deliver_library_email(**payload)
        return {"delivered": True}
    if job_type == BackgroundJob.TYPE_PHYSICAL_IMPORT:
        from .imports import import_physical_rows

        result = import_physical_rows(payload.get("rows", []))
        return {
            "success": result.success_count > 0 or not result.errors,
            "success_count": result.success_count,
            "error_count": len(result.errors),
            "errors": result.errors[:30],
        }
    raise ValueError("unsupported_background_job_type")


def _record_success(job_id: int, result: dict) -> None:
    BackgroundJob.objects.filter(pk=job_id).update(
        status=BackgroundJob.STATUS_COMPLETED,
        result=result,
        payload={},
        completed_at=timezone.now(),
        locked_at=None,
        last_error_code="",
    )


def _record_failure(job_id: int, exc: Exception) -> None:
    with transaction.atomic():
        job = BackgroundJob.objects.select_for_update().get(pk=job_id)
        error_code = exc.__class__.__name__[:100]
        if job.attempts >= job.max_attempts:
            job.status = BackgroundJob.STATUS_FAILED
            job.completed_at = timezone.now()
            job.payload = {}
        else:
            delay = min(_RETRY_BASE_SECONDS * (2 ** max(job.attempts - 1, 0)), _RETRY_MAX_SECONDS)
            job.status = BackgroundJob.STATUS_QUEUED
            job.available_at = timezone.now() + timedelta(seconds=delay)
        job.locked_at = None
        job.last_error_code = error_code
        job.save(
            update_fields=[
                "status", "available_at", "locked_at", "last_error_code",
                "completed_at", "payload", "updated_at",
            ]
        )
    logger.error(
        "background_job_failed",
        extra={"event": "background_job_failed", "job_type": job.job_type, "error_code": error_code},
    )


def job_public_result(job: BackgroundJob) -> dict:
    """Return a response-safe status without exposing queued payload data."""
    return {
        "id": job.pk,
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "result": job.result if job.status == BackgroundJob.STATUS_COMPLETED else {},
        "error_code": job.last_error_code if job.status == BackgroundJob.STATUS_FAILED else "",
    }
