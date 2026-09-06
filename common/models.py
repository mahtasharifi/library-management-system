"""Infrastructure persistence shared across project domains."""

from django.db import models


class RateLimitBucket(models.Model):
    """Shared fixed-window counter used for abuse-sensitive endpoints."""

    namespace = models.CharField(max_length=64)
    identifier_hash = models.CharField(max_length=32)
    window_started_at = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "rate_limit_buckets"
        constraints = [
            models.UniqueConstraint(
                fields=["namespace", "identifier_hash", "window_started_at"],
                name="unique_rate_limit_window",
            ),
        ]
        indexes = [
            models.Index(fields=["namespace", "window_started_at"], name="rate_limit_cleanup_idx"),
        ]
