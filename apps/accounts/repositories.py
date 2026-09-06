"""Persistence queries owned by the accounts domain."""

from __future__ import annotations

from .models import UserProfile


def get_or_create_profile(user):
    return UserProfile.objects.get_or_create(user=user)[0]


def notification_count(user, *, unread_only: bool = False) -> int:
    queryset = user.library_notifications.all()
    if unread_only:
        queryset = queryset.filter(is_read=False)
    return queryset.count()


def recent_notifications(user, *, limit: int = 5):
    return list(user.library_notifications.all()[:limit])


def notification_queryset(user, *, unread_only: bool = False):
    queryset = user.library_notifications.all()
    return queryset.filter(is_read=False) if unread_only else queryset


def user_request_history(user):
    digital = user.digital_book_requests.select_related("book").all()
    physical = user.physical_book_requests.select_related("book").all()
    return digital, physical
