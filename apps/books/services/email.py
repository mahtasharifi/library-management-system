"""Queued email delivery for library workflows."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from common.i18n import translate as t

from .notifications import owner_for


def site_url(path: str = "/library/") -> str:
    return f"{settings.SITE_URL.rstrip('/')}/{path.lstrip('/')}"


def record_email(record) -> str:
    email = (getattr(record, "email", "") or "").strip()
    owner = owner_for(record)
    return email or ((owner.email or "").strip() if owner else "")


def _email_payload(
    recipient: str,
    subject: str,
    heading: str,
    message: str,
    *,
    eyebrow: str | None = None,
    action_label: str = "",
    action_url: str = "",
    details=None,
) -> dict:
    return {
        "recipient": recipient.strip(),
        "subject": subject,
        "heading": heading,
        "message": message,
        "eyebrow": eyebrow or t("email.library.eyebrow"),
        "action_label": action_label,
        "action_url": action_url,
        "details": details or [],
    }


def send_library_email(
    recipient: str,
    subject: str,
    heading: str,
    message: str,
    *,
    eyebrow: str | None = None,
    action_label: str = "",
    action_url: str = "",
    details=None,
) -> bool:
    """Queue delivery and return whether the job was accepted."""
    recipient = (recipient or "").strip()
    if not recipient:
        return False
    from ..models import BackgroundJob
    from .jobs import enqueue_job

    enqueue_job(
        BackgroundJob.TYPE_EMAIL,
        _email_payload(
            recipient,
            subject,
            heading,
            message,
            eyebrow=eyebrow,
            action_label=action_label,
            action_url=action_url,
            details=details,
        ),
        # SMTP has no portable idempotency key. Automatic retries could duplicate
        # a message if delivery succeeded but the worker crashed before commit.
        # Keep email jobs at-most-once; operators can explicitly re-send a failed job.
        max_attempts=1,
    )
    return True


def deliver_library_email(
    recipient: str,
    subject: str,
    heading: str,
    message: str,
    *,
    eyebrow: str | None = None,
    action_label: str = "",
    action_url: str = "",
    details=None,
) -> None:
    """Perform one delivery attempt; failures are handled by the job retry policy."""
    context = {
        "subject": subject,
        "heading": heading,
        "message": message,
        "eyebrow": eyebrow or t("email.library.eyebrow"),
        "action_label": action_label,
        "action_url": action_url,
        "details": details or [],
        "library_url": site_url("/library/"),
    }
    sent = send_mail(
        subject=subject,
        message=f"{heading}\n\n{message}" + (f"\n\n{action_url}" if action_url else ""),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        html_message=render_to_string("books/emails/library-message.html", context),
        fail_silently=False,
    )
    if sent != 1:
        raise RuntimeError("email_delivery_not_accepted")


def send_book_email(book, email: str) -> bool:
    if not book.has_pdf:
        return False
    protected_url = site_url(reverse("book_pdf_download", args=[book.pk]))
    return send_library_email(
        email,
        t("email.pdf.subject", title=book.title),
        t("email.pdf.heading"),
        t("email.pdf.message"),
        eyebrow=t("email.pdf.eyebrow"),
        action_label=t("email.pdf.action"),
        action_url=protected_url,
        details=[{"label": t("common.labels.book"), "value": book.title}, {"label": t("common.labels.author"), "value": book.author or t("common.none")}],
    )
