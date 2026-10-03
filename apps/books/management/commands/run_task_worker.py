"""Run the durable background-job worker."""

from __future__ import annotations

import os
import socket
import time
from datetime import timedelta

from django.conf import settings
from django.core.management import BaseCommand
from django.utils import timezone

from apps.books.models import TaskWorkerHeartbeat
from apps.books.services.jobs import process_next_job, recover_stale_jobs
from common.security import purge_expired_rate_limits


class Command(BaseCommand):
    help = "Process queued library background jobs with bounded retries."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process at most one job and exit.")
        parser.add_argument("--poll-interval", type=float, default=2.0)
        parser.add_argument("--worker-name", default="")

    def handle(self, *args, **options):
        worker_name = options["worker_name"] or f"{socket.gethostname()}:{os.getpid()}"
        poll_interval = min(max(options["poll_interval"], 0.25), 60.0)
        next_maintenance = 0.0
        while True:
            TaskWorkerHeartbeat.objects.update_or_create(
                worker_name=worker_name,
                defaults={"seen_at": timezone.now()},
            )
            processed = process_next_job()
            now_monotonic = time.monotonic()
            if now_monotonic >= next_maintenance:
                self._maintenance()
                next_maintenance = now_monotonic + 3600
            if options["once"]:
                return
            if not processed:
                time.sleep(poll_interval)

    def _maintenance(self):
        from apps.books.models import BackgroundJob

        purge_expired_rate_limits(older_than_seconds=86400)
        recover_stale_jobs()
        retention_days = min(max(settings.BACKGROUND_JOB_RETENTION_DAYS, 1), 365)
        cutoff = timezone.now() - timedelta(days=retention_days)
        BackgroundJob.objects.filter(
            status__in=[BackgroundJob.STATUS_COMPLETED, BackgroundJob.STATUS_FAILED],
            completed_at__lt=cutoff,
        ).delete()
