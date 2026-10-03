"""Small process-local HTTP metrics registry used without adding a monitoring dependency."""

from __future__ import annotations

import threading

_lock = threading.Lock()
_request_count = 0
_error_count = 0
_total_response_seconds = 0.0


def record_request(status_code: int, elapsed_seconds: float) -> None:
    global _request_count, _error_count, _total_response_seconds
    with _lock:
        _request_count += 1
        _error_count += int(status_code >= 500)
        _total_response_seconds += max(elapsed_seconds, 0.0)


def snapshot() -> dict:
    with _lock:
        average_ms = (_total_response_seconds / _request_count * 1000) if _request_count else 0.0
        return {
            "request_count": _request_count,
            "server_error_count": _error_count,
            "average_response_ms": round(average_ms, 3),
        }
