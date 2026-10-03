from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="RateLimitBucket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("namespace", models.CharField(max_length=64)),
                ("identifier_hash", models.CharField(max_length=32)),
                ("window_started_at", models.DateTimeField()),
                ("count", models.PositiveIntegerField(default=0)),
            ],
            options={"db_table": "rate_limit_buckets"},
        ),
        migrations.AddConstraint(
            model_name="ratelimitbucket",
            constraint=models.UniqueConstraint(fields=("namespace", "identifier_hash", "window_started_at"), name="unique_rate_limit_window"),
        ),
        migrations.AddIndex(
            model_name="ratelimitbucket",
            index=models.Index(fields=["namespace", "window_started_at"], name="rate_limit_cleanup_idx"),
        ),
    ]
