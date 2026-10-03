"""Safe request parsing helpers."""

from __future__ import annotations

import json
from django.core.exceptions import ValidationError
from common.i18n import translate as t


def parse_json_value(request):
    """Decode a JSON request body without assuming the top-level shape."""
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValidationError(t("request.validation.invalid_json")) from exc


def parse_json_object(request) -> dict:
    payload = parse_json_value(request)
    if not isinstance(payload, dict):
        raise ValidationError(t("request.validation.object_required"))
    return payload


def parse_json_array(request) -> list:
    payload = parse_json_value(request)
    if not isinstance(payload, list):
        raise ValidationError(t("request.validation.array_required"))
    return payload


def form_errors(form) -> str:
    messages: list[str] = []
    for field, errors in form.errors.items():
        for error in errors:
            messages.append(str(error))
    return " ".join(messages) or t("request.validation.invalid_data")
