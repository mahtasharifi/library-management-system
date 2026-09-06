from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import RateLimitBucket
from .security import check_rate_limit


class SharedRateLimitTests(TestCase):
    def test_limit_is_persisted_in_database(self):
        self.assertTrue(check_rate_limit('login', 'User@Example.com', limit=2, window_seconds=60).allowed)
        self.assertTrue(check_rate_limit('login', 'user@example.com', limit=2, window_seconds=60).allowed)
        blocked = check_rate_limit('login', 'USER@example.com', limit=2, window_seconds=60)
        self.assertFalse(blocked.allowed)
        self.assertGreater(blocked.retry_after, 0)
        self.assertEqual(RateLimitBucket.objects.count(), 1)
        self.assertEqual(RateLimitBucket.objects.get().count, 2)

    def test_rate_limiter_fails_closed_when_backend_is_unavailable(self):
        with patch.object(RateLimitBucket.objects, 'get_or_create', side_effect=DatabaseError('database detail')):
            result = check_rate_limit('mfa', 'identifier', limit=5, window_seconds=60)
        self.assertFalse(result.allowed)
        self.assertEqual(result.retry_after, 60)


class MetricsEndpointTests(TestCase):
    @override_settings(METRICS_TOKEN='metrics-secret')
    def test_metrics_requires_staff_or_bearer_token(self):
        hidden = self.client.get(reverse('metrics'))
        self.assertEqual(hidden.status_code, 404)

        response = self.client.get(
            reverse('metrics'),
            HTTP_AUTHORIZATION='Bearer metrics-secret',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('request_count', payload)
        self.assertIn('database_latency_ms', payload)
        self.assertIn('background_queue_depth', payload)
        self.assertIn('background_worker_available', payload)


class StructuredLoggingTests(TestCase):
    def test_formatter_includes_only_whitelisted_security_context(self):
        import json
        import logging
        from .logging import JsonFormatter

        record = logging.LogRecord(
            name="security", level=logging.INFO, pathname=__file__, lineno=1,
            msg="admin_action", args=(), exc_info=None,
        )
        record.event = "admin_action"
        record.actor = "abcdef123456"
        record.method = "POST"
        record.path = "/api/admin/books/1/"
        record.status_code = 200
        record.password = "must-not-appear"
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload["event"], "admin_action")
        self.assertEqual(payload["actor"], "abcdef123456")
        self.assertEqual(payload["method"], "POST")
        self.assertEqual(payload["status_code"], 200)
        self.assertNotIn("password", payload)
        self.assertNotIn("must-not-appear", json.dumps(payload))
