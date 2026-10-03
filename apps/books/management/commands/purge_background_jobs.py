"""Delete old completed/failed background-job metadata according to retention policy."""

from datetime import timedelta

from django.core.management import BaseCommand
from django.utils import timezone

from apps.books.models import BackgroundJob


class Command(BaseCommand):
    help = "Purge finished background-job metadata older than the configured retention window."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        days = min(max(options["days"], 1), 365)
        cutoff = timezone.now() - timedelta(days=days)
        count, _ = BackgroundJob.objects.filter(
            status__in=[BackgroundJob.STATUS_COMPLETED, BackgroundJob.STATUS_FAILED],
            completed_at__lt=cutoff,
        ).delete()
        self.stdout.write(self.style.SUCCESS(f"Purged {count} old background-job rows."))
