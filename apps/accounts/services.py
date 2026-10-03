"""Business services for account/profile pages."""

from __future__ import annotations

from . import repositories


def account_context(user, **extra):
    return {"unread_notifications": repositories.notification_count(user, unread_only=True), **extra}


def profile_context(user):
    profile = repositories.get_or_create_profile(user)
    digital, physical = repositories.user_request_history(user)
    return account_context(
        user,
        profile=profile,
        digital_requests=digital[:5],
        physical_requests=physical[:5],
        digital_count=digital.count(),
        physical_count=physical.count(),
        pending_count=digital.filter(status="pending").count() + physical.filter(status="pending").count(),
    )


def notification_payload(notification):
    return {
        "id": notification.id,
        "kind": notification.kind,
        "title": notification.title,
        "message": notification.message,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
    }
