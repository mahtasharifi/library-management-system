"""Presentation-ready catalog and book-detail data."""

from __future__ import annotations

import re

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404

from common.i18n import translate as t

from ..repositories import catalog as catalog_repository
from .serialization import serialize_book
from . import nbok as nbok_service

CATALOG_PAGE_SIZE = 48
API_PAGE_SIZE_DEFAULT = 24
API_PAGE_SIZE_MAX = 50


def normalize_availability(value: str) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in {"available", "borrowed"} else ""


def parse_category_id(value: str) -> int | None:
    return int(value) if str(value or "").isdigit() else None


def parse_public_category(value: str) -> tuple[int, str] | None:
    """Parse a stable public NBOK selector such as ``12-L3``."""
    match = re.fullmatch(r"([1-9]\d*)-(L[1-6])", str(value or "").strip().upper())
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def public_category_tree() -> list[dict]:
    """Return NBOK nodes with URL-safe ids for the public catalog/home page."""
    def convert(node: dict, depth: int = 0) -> dict:
        public_id = f"{node['row_id']}-{node['level_code']}"
        return {
            "id": public_id,
            "row_id": node["row_id"],
            "level_code": node["level_code"],
            "depth": depth,
            "name": node["name"],
            "path_text": node.get("path_text", ""),
            "book_count": node.get("book_count", 0),
            "children": [convert(child, depth + 1) for child in node.get("children", [])],
        }

    # Public navigation intentionally contains only categories that have books
    # assigned directly to that exact NBOK level.  No empty/ancestor-only nodes.
    return [convert(node) for node in nbok_service.directly_used_nodes()]


def flatten_public_categories(nodes: list[dict]) -> list[dict]:
    result: list[dict] = []
    def walk(items):
        for item in items:
            result.append(item)
            walk(item.get("children", []))
    walk(nodes)
    return result


def find_public_category(nodes: list[dict], category_id: str) -> dict | None:
    return next((node for node in flatten_public_categories(nodes) if node["id"] == category_id), None)


def apply_shelf_metadata(book) -> None:
    seed = abs(book.pk)
    book.shelf_color_class = f"shelf-color-{seed % 10}"
    book.shelf_size_class = f"shelf-size-{seed % 5}"
    if book.has_physical and book.physical_available > 0:
        borrowed = max(0, book.physical_count - book.physical_available)
        book.availability_label = t("books.availability.physical_counts", available=book.physical_available, borrowed=borrowed) if borrowed else t("books.availability.available")
        book.availability_class = "available"
    elif book.has_physical:
        book.availability_label = t("books.availability.borrowed")
        book.availability_class = "borrowed"
    elif book.has_pdf:
        book.availability_label = t("books.availability.digital")
        book.availability_class = "digital"
    else:
        book.availability_label = t("books.availability.unknown")
        book.availability_class = "unknown"


def catalog_page(*, search: str, category_id, availability: str, page_number: int | str = 1) -> dict:
    categories_tree = public_category_tree()
    category_value = str(category_id or "")
    selected_category = find_public_category(categories_tree, category_value)
    parsed = parse_public_category(category_value) if selected_category else None
    queryset = catalog_repository.filtered_books(
        search=search,
        nbok_row_id=parsed[0] if parsed else None,
        nbok_level=parsed[1] if parsed else None,
        availability=availability,
    )
    paginator = Paginator(queryset, CATALOG_PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    books = list(page_obj.object_list)
    for book in books:
        apply_shelf_metadata(book)
    return {
        "books": books,
        "page_obj": page_obj,
        "categories": flatten_public_categories(categories_tree),
        "selected_category": selected_category,
        "search_query": search,
        "availability": availability,
    }


def book_detail_context(book_id: int, user) -> dict:
    book = get_object_or_404(catalog_repository.book_detail_queryset(), pk=book_id)
    user_rating = book.ratings.filter(user=user).values_list("rating", flat=True).first()
    current_borrow = book.active_borrows_cache[0] if book.active_borrows_cache else None
    if book.has_physical and book.physical_available > 0:
        borrowed = max(0, book.physical_count - book.physical_available)
        label = t("books.availability.ready_copies", available=book.physical_available)
        if borrowed:
            label += t("books.availability.borrowed_copies_suffix", borrowed=borrowed)
        availability_class = "available"
    elif book.has_physical:
        label, availability_class = t("books.availability.currently_borrowed"), "borrowed"
    elif book.has_pdf:
        label, availability_class = t("books.availability.digital_available"), "digital"
    else:
        label, availability_class = t("books.availability.not_recorded"), "unknown"
    return {
        "book": book,
        "comments": catalog_repository.approved_comments(book),
        "current_borrow": current_borrow,
        "average_rating": round(float(book.average_rating), 1) if book.average_rating is not None else None,
        "rating_count": book.rating_total,
        "user_rating": user_rating,
        "availability_label": label,
        "availability_class": availability_class,
        "detail_book_data": serialize_book(book),
    }


def category_tree() -> list[dict]:
    """Return the category hierarchy with aggregate descendant book counts."""
    items = catalog_repository.categories_with_parents()
    direct_counts = catalog_repository.category_direct_counts()
    nodes = {
        item.id: {
            "id": item.id,
            "name": item.name,
            "parent_id": item.parent_id,
            "book_count": direct_counts.get(item.id, 0),
            "children": [],
        }
        for item in items
    }
    roots: list[dict] = []
    for item in items:
        node = nodes[item.id]
        if item.parent_id in nodes:
            nodes[item.parent_id]["children"].append(node)
        else:
            roots.append(node)

    def aggregate(node: dict) -> int:
        node["book_count"] += sum(aggregate(child) for child in node["children"])
        return node["book_count"]

    for root in roots:
        aggregate(root)
    return roots
