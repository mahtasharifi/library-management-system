"""Authorization and CDN URL handling for digital book downloads."""

from __future__ import annotations

from django.core.exceptions import ValidationError

from ..models import BookRequest
from .storage import is_managed_asset_url


def can_download_book(user, book) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False):
        return True
    return BookRequest.objects.filter(
        book=book,
        user=user,
        status="approved",
    ).exists()


def public_pdf_url(book) -> str:
    url = str(book.pdf_url or "").strip()
    if not url or not is_managed_asset_url(url, "pdf"):
        raise ValidationError("public_pdf_not_ready")
    return url
