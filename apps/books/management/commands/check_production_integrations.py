"""Live checks for production dependencies and deployment invariants."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import tempfile

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.management import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.books.models import BackgroundJob, TaskWorkerHeartbeat
from apps.books.services.storage import _ftp_client, _ftp_enter_root

PROJECT_TABLES = {
    "user_profiles", "mfa_credentials", "rate_limit_buckets",
    "book_categories", "books", "physical_book_borrows", "physical_book_requests",
    "digital_book_requests", "library_messages", "book_questions", "book_comments",
    "book_ratings", "user_notifications", "background_jobs", "task_worker_heartbeats",
}
DANGEROUS_RUNTIME_GRANTS = {
    "ALL PRIVILEGES", "SUPER", "CREATE", "ALTER", "DROP", "INDEX",
    "REFERENCES", "TRIGGER", "EVENT", "CREATE USER", "GRANT OPTION", "FILE",
}


class Command(BaseCommand):
    help = "Check database, schema, email, storage, migrations and background-worker connectivity."

    def add_arguments(self, parser):
        parser.add_argument("--send-test-email", metavar="ADDRESS", default="")
        parser.add_argument("--skip-worker", action="store_true")

    def handle(self, *args, **options):
        failures: list[str] = []
        self._check_database(failures)
        self._check_migrations(failures)
        self._check_mysql_schema(failures)
        self._check_runtime_grants(failures)
        self._check_email(failures, options["send_test_email"])
        self._check_storage(failures)
        if not options["skip_worker"]:
            self._check_worker(failures)
        if failures:
            raise CommandError("Production integration checks failed: " + "; ".join(failures))
        self.stdout.write(self.style.SUCCESS("All requested production integration checks passed."))

    def _check_database(self, failures):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            self.stdout.write(self.style.SUCCESS("database: ok"))
        except Exception as exc:
            failures.append(f"database ({exc.__class__.__name__})")

    def _check_migrations(self, failures):
        try:
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                failures.append("migrations (pending)")
            else:
                self.stdout.write(self.style.SUCCESS("migrations: current"))
        except Exception as exc:
            failures.append(f"migrations ({exc.__class__.__name__})")

    def _check_mysql_schema(self, failures):
        if connection.vendor != "mysql":
            self.stdout.write("mysql schema: skipped on non-MySQL backend")
            return
        try:
            placeholders = ",".join(["%s"] * len(PROJECT_TABLES))
            query = (
                "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
                f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ({placeholders})"
            )
            with connection.cursor() as cursor:
                cursor.execute(query, sorted(PROJECT_TABLES))
                rows = cursor.fetchall()
            bad = [name for name, engine in rows if str(engine).upper() != "INNODB"]
            missing = PROJECT_TABLES - {name for name, _engine in rows}
            if bad:
                failures.append("mysql schema (non-InnoDB project tables)")
            elif missing:
                failures.append("mysql schema (missing migrated project tables)")
            else:
                self.stdout.write(self.style.SUCCESS("mysql schema: InnoDB/current"))
        except Exception as exc:
            failures.append(f"mysql schema ({exc.__class__.__name__})")

    def _check_runtime_grants(self, failures):
        if connection.vendor != "mysql" or getattr(settings, "DJANGO_MIGRATION_MODE", False):
            return
        try:
            with connection.cursor() as cursor:
                cursor.execute("SHOW GRANTS FOR CURRENT_USER")
                grants = " ".join(str(row[0]).upper() for row in cursor.fetchall())
            if any(grant in grants for grant in DANGEROUS_RUNTIME_GRANTS):
                failures.append("database privileges (runtime account is over-privileged)")
            else:
                self.stdout.write(self.style.SUCCESS("database privileges: runtime-safe"))
        except Exception as exc:
            failures.append(f"database privileges ({exc.__class__.__name__})")

    def _check_email(self, failures, recipient):
        connection_obj = None
        try:
            connection_obj = get_connection()
            connection_obj.open()
            self.stdout.write(self.style.SUCCESS("email transport: ok"))
            if recipient:
                sent = send_mail(
                    "Library production test",
                    "This is an explicit production integration test.",
                    settings.DEFAULT_FROM_EMAIL,
                    [recipient],
                    fail_silently=False,
                )
                if sent != 1:
                    raise RuntimeError("test_email_not_accepted")
                self.stdout.write(self.style.SUCCESS("test email: sent"))
        except Exception as exc:
            failures.append(f"email ({exc.__class__.__name__})")
        finally:
            if connection_obj is not None:
                try:
                    connection_obj.close()
                except Exception:
                    pass

    def _check_storage(self, failures):
        mode = str(settings.LIBRARY_CDN_STORAGE).strip().lower()
        if mode == "filesystem":
            root = Path(settings.LIBRARY_CDN_ROOT)
            try:
                root.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=root, prefix=".health-", delete=True):
                    pass
                self.stdout.write(self.style.SUCCESS("filesystem storage: ok"))
            except OSError as exc:
                failures.append(f"filesystem storage ({exc.__class__.__name__})")
            return
        if mode == "ftp":
            ftp = None
            try:
                ftp = _ftp_client()
                _ftp_enter_root(ftp)
                for folder in ("Cover", "PDF"):
                    ftp.cwd(folder)
                    ftp.cwd("..")
                self.stdout.write(self.style.SUCCESS("FTPS Cover/PDF storage: ok"))
            except Exception as exc:
                failures.append(f"FTPS storage ({exc.__class__.__name__})")
            finally:
                if ftp is not None:
                    try:
                        ftp.quit()
                    except Exception:
                        ftp.close()
            return
        failures.append("storage mode (unsupported)")

    def _check_worker(self, failures):
        try:
            cutoff = timezone.now() - timedelta(seconds=settings.BACKGROUND_WORKER_MAX_AGE_SECONDS)
            if not TaskWorkerHeartbeat.objects.filter(seen_at__gte=cutoff).exists():
                failures.append("background worker (no recent heartbeat)")
                return
            failed = BackgroundJob.objects.filter(status=BackgroundJob.STATUS_FAILED).count()
            if failed:
                failures.append("background worker (failed jobs require review)")
                return
            self.stdout.write(self.style.SUCCESS("background worker: ok"))
        except Exception as exc:
            failures.append(f"background worker ({exc.__class__.__name__})")
