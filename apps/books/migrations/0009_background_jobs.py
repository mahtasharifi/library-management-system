from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("books", "0008_legacy_mysql_integrity"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BackgroundJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("job_type", models.CharField(choices=[("email", "ارسال ایمیل"), ("physical_import", "درون‌ریزی کتاب فیزیکی")], max_length=40)),
                ("payload", models.JSONField(default=dict)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("queued", "در صف"), ("running", "در حال اجرا"), ("completed", "تکمیل شده"), ("failed", "ناموفق")], default="queued", max_length=20)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=5)),
                ("available_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("locked_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="library_background_jobs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "background_jobs", "ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="TaskWorkerHeartbeat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("worker_name", models.CharField(max_length=100, unique=True)),
                ("seen_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={"db_table": "task_worker_heartbeats", "ordering": ["worker_name"]},
        ),
        migrations.AddIndex(model_name="backgroundjob", index=models.Index(fields=["status", "available_at", "created_at"], name="background_job_queue_idx")),
        migrations.AddIndex(model_name="backgroundjob", index=models.Index(fields=["job_type", "status", "-created_at"], name="background_job_type_idx")),
        migrations.AddConstraint(model_name="backgroundjob", constraint=models.CheckConstraint(condition=models.Q(status__in=["queued", "running", "completed", "failed"]), name="background_job_valid_status")),
        migrations.AddConstraint(model_name="backgroundjob", constraint=models.CheckConstraint(condition=models.Q(max_attempts__gte=1), name="background_job_attempts_positive")),
    ]
