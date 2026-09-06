"""Notification workflows shared by administrative services."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.utils import timezone

from common.i18n import translate as t

from ..models import Message, UserNotification


def owner_for(record):
    if getattr(record, "user_id", None):
        return record.user
    email = (getattr(record, "email", "") or "").strip()
    return User.objects.filter(email__iexact=email).first() if email else None


def notify(record, kind: str, title: str, text: str) -> None:
    user = owner_for(record)
    if not user:
        return
    related_type = record._meta.model_name
    if kind == "read" and UserNotification.objects.filter(
        user=user, kind="read", related_type=related_type, related_id=record.pk
    ).exists():
        return
    UserNotification.objects.create(
        user=user,
        kind=kind,
        title=title,
        message=text,
        related_type=related_type,
        related_id=record.pk,
    )


def mark_admin_read(record, label: str | None = None) -> None:
    label = label or t("notifications.default_label")
    fields: list[str] = []
    if hasattr(record, "admin_read_at") and not record.admin_read_at:
        record.admin_read_at = timezone.now()
        fields.append("admin_read_at")
    if isinstance(record, Message) and not record.is_read:
        record.is_read = True
        fields.append("is_read")
    if not fields:
        return
    record.save(update_fields=fields)
    notify(record, "read", t("notifications.admin_read_title"), t("notifications.admin_read_message", label=label))


def respond(record, kind: str, title: str, response_text: str) -> None:
    record.admin_response = response_text
    record.responded_at = timezone.now()
    fields = ["admin_response", "responded_at"]
    if hasattr(record, "admin_read_at") and not record.admin_read_at:
        record.admin_read_at = timezone.now()
        fields.append("admin_read_at")
    if isinstance(record, Message) and not record.is_read:
        record.is_read = True
        fields.append("is_read")
    record.save(update_fields=fields)
    notify(record, kind, title, response_text)
