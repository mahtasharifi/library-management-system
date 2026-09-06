"""Explicit response serializers for the books domain."""

from __future__ import annotations

from django.db.models import Avg


def category_path_ids(category, parent_map: dict[int, int | None]) -> list[int]:
    path: list[int] = []
    guard: set[int] = set()
    current_id = category.id if category else None
    while current_id and current_id not in guard:
        guard.add(current_id)
        path.insert(0, current_id)
        current_id = parent_map.get(current_id)
    return path


def _rating_values(book) -> tuple[float | None, int]:
    has_average_annotation = hasattr(book, "average_rating")
    has_count_annotation = hasattr(book, "rating_total")
    average_rating = getattr(book, "average_rating", None)
    rating_count = getattr(book, "rating_total", None)
    if not has_average_annotation:
        average_rating = book.ratings.aggregate(value=Avg("rating"))["value"]
    if not has_count_annotation:
        rating_count = book.ratings.count()
    return average_rating, int(rating_count or 0)


def _current_borrow(book):
    active_borrows = getattr(book, "active_borrows_cache", None)
    if active_borrows is not None:
        return active_borrows[0] if active_borrows else None
    return book.borrows.filter(is_returned=False).only("borrower_name").first()


def serialize_book(book, parent_map: dict[int, int | None] | None = None, *, include_admin: bool = False) -> dict:
    parent_map = parent_map or {}
    category = getattr(book, "category", None)
    display_category = getattr(book, "display_category_name", "")
    current_borrow = _current_borrow(book)
    average_rating, rating_count = _rating_values(book)
    created_at = getattr(book, "created_at", None)
    updated_at = getattr(book, "updated_at", None)
    data = {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "translator": book.translator,
        "publisher": book.publisher,
        "library": book.library,
        "category_id": book.category_id,
        "category": display_category,
        "category_id_path": category_path_ids(category, parent_map),
        "summary": book.summary,
        "cover_url": book.cover_url or "",
        "tags": book.tags,
        "has_pdf": book.has_pdf,
        "has_physical": book.has_physical,
        "physical_count": book.physical_count,
        "physical_available": book.physical_available,
        "average_rating": round(float(average_rating), 1) if average_rating is not None else None,
        "rating_count": rating_count,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }
    if include_admin:
        from .nbok import selection as nbok_selection
        selected_nbok = nbok_selection(getattr(book, "nbok_category", None), getattr(book, "nbok_category_level", None))
        data.update({
            "nbok_category_id": book.nbok_category_id,
            "nbok_category_level": book.nbok_category_level or "",
            "nbok_category": selected_nbok["name"] if selected_nbok else "",
            "nbok_category_path": selected_nbok["path_text"] if selected_nbok else "",
            "pdf_url": book.pdf_url or "",
            "physical_location": book.physical_location,
            "current_borrower": current_borrow.borrower_name if current_borrow else None,
            "request_count": book.request_count,
        })
    return data
