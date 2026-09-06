"""Public library business workflows."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Avg, Count, F

from common.security import get_client_ip
from common.i18n import translate as t
from ..models import Book, BookComment, BookRating, BookRequest, Message, PhysicalBookRequest


def preferred_email(user, submitted: str | None) -> str:
    email = (submitted or user.email or "").strip()
    if not email:
        raise ValidationError(t("books.public.validation.account_email_missing"))
    validate_email(email)
    return email


@transaction.atomic
def request_digital_book(user, *, book_id: int, email: str | None, request) -> BookRequest:
    book = Book.objects.filter(pk=book_id).first()
    if not book:
        raise Book.DoesNotExist
    if not book.has_pdf:
        raise ValidationError(t("books.public.validation.pdf_missing"))
    record = BookRequest.objects.create(
        book=book,
        user=user,
        name=user.get_full_name() or user.username,
        email=preferred_email(user, email),
        ip_address=get_client_ip(request),
    )
    Book.objects.filter(pk=book.pk).update(request_count=F("request_count") + 1)
    return record


@transaction.atomic
def request_physical_book(user, *, book_id: int, name: str, email: str | None, phone: str, message: str) -> tuple[PhysicalBookRequest, bool]:
    book = Book.objects.filter(pk=book_id).first()
    if not book:
        raise Book.DoesNotExist
    if not book.has_physical:
        raise ValidationError(t("books.public.validation.physical_missing"))
    record = PhysicalBookRequest.objects.create(
        book=book,
        user=user,
        name=(name or user.get_full_name() or user.username).strip(),
        email=preferred_email(user, email),
        phone=phone.strip(),
        message=message.strip(),
    )
    return record, book.physical_available > 0


def create_contact_message(user, cleaned_data: dict) -> Message:
    message_type = cleaned_data.get("type") or "book_request"
    email = preferred_email(user, cleaned_data.get("email"))
    if message_type == "contact":
        subject = (cleaned_data.get("subject") or "").strip()
        text = (cleaned_data.get("message") or "").strip()
        if not subject or not text:
            raise ValidationError(t("books.public.validation.contact_required"))
        topic = (cleaned_data.get("topic") or t("books.public.contact.default_topic")).strip()
        body = t("books.public.contact.body", topic=topic, subject=subject, text=text)
    else:
        subject = (cleaned_data.get("message") or "").strip()
        if not subject:
            raise ValidationError(t("books.public.validation.book_request_required"))
        body = t("books.public.book_request.body", subject=subject)
        reason = (cleaned_data.get("reason") or "").strip()
        if reason:
            body += t("books.public.book_request.reason", reason=reason)
    return Message.objects.create(
        user=user,
        name=(cleaned_data.get("name") or user.get_full_name() or user.username).strip(),
        email=email,
        message=body,
    )


def create_comment(user, *, book_id: int, name: str, email: str | None, text: str) -> BookComment:
    book = Book.objects.filter(pk=book_id).first()
    if not book:
        raise Book.DoesNotExist
    return BookComment.objects.create(
        book=book,
        name=(name or user.get_full_name() or user.username).strip(),
        email=preferred_email(user, email),
        comment=text.strip(),
    )


def create_comment_reply(user, *, parent_id: int, name: str, email: str | None, text: str) -> BookComment:
    parent = BookComment.objects.filter(pk=parent_id).select_related("book").first()
    if not parent:
        raise BookComment.DoesNotExist
    return BookComment.objects.create(
        book=parent.book,
        parent=parent,
        name=(name or user.get_full_name() or user.username).strip(),
        email=preferred_email(user, email),
        comment=text.strip(),
    )


@transaction.atomic
def rate_book(user, *, book_id: int, rating: int, request) -> dict:
    book = Book.objects.filter(pk=book_id).first()
    if not book:
        raise Book.DoesNotExist
    BookRating.objects.update_or_create(
        book=book,
        user=user,
        defaults={"rating": rating, "user_ip": get_client_ip(request)},
    )
    stats = book.ratings.aggregate(average=Avg("rating"), count=Count("id"))
    return {
        "user_rating": rating,
        "average_rating": round(float(stats["average"]), 1),
        "rating_count": stats["count"],
    }
