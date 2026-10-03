"""Structured JSON logging without external dependencies."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from .request_context import request_id_var


class JsonFormatter(logging.Formatter):
    """Render safe, structured log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        safe_extra_fields = (
            "event", "actor", "method", "path", "status_code", "count",
            "job_type", "error_code", "recovery", "subject_hash",
        )
        for field in safe_extra_fields:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
