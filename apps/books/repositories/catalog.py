"""Read-only queries for the public book catalog."""

from __future__ import annotations

from django.db.models import Avg, Count, F, Prefetch, Q

from ..models import Book, BookComment, Category, NBOKEntry, PhysicalBookBorrow


def categories_with_parents():
    return list(Category.objects.select_related("parent").order_by("name"))


def category_parent_map():
    return dict(Category.objects.values_list("id", "parent_id"))


def category_descendant_ids(categories, root_id: int) -> set[int]:
    descendants = {root_id}
    for category in categories:
        current = category.parent_id
        seen: set[int] = set()
        while current and current not in seen:
            if current == root_id:
                descendants.add(category.id)
                break
            seen.add(current)
            current = next((item.parent_id for item in categories if item.id == current), None)
    return descendants


NBOK_LEVELS = ("L1", "L2", "L3", "L4", "L5", "L6")


def base_book_queryset():
    active_borrows = PhysicalBookBorrow.objects.filter(is_returned=False)
    return (
        Book.objects.select_related("category", "nbok_category")
        .prefetch_related(Prefetch("borrows", queryset=active_borrows, to_attr="active_borrows_cache"))
        .annotate(average_rating=Avg("ratings__rating"), rating_total=Count("ratings", distinct=True))
        .order_by("-created_at", "-id")
    )


def _nbok_filter(queryset, *, row_id: int, level: str):
    level = str(level or "").upper()
    if level not in NBOK_LEVELS:
        return queryset.none()
    entry = NBOKEntry.objects.filter(id=row_id).first()
    if entry is None:
        return queryset.none()

    # Public category filtering is exact: a category represents the precise
    # NBOK level selected for a book, not all of its descendants.  Path fields
    # still identify the conceptual node when several NBOK rows share it.
    path_filters = {}
    for current in NBOK_LEVELS[: NBOK_LEVELS.index(level) + 1]:
        value = getattr(entry, current.lower(), None)
        if value and str(value).strip():
            path_filters[f"nbok_category__{current.lower()}"] = str(value).strip()
    if not path_filters or not getattr(entry, level.lower(), None):
        return queryset.none()

    return queryset.filter(nbok_category_level=level, **path_filters)


def filtered_books(
    *,
    search: str = "",
    category_id: int | None = None,
    nbok_row_id: int | None = None,
    nbok_level: str | None = None,
    availability: str = "",
):
    queryset = base_book_queryset()
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(author__icontains=search)
            | Q(translator__icontains=search)
            | Q(publisher__icontains=search)
            | Q(category__name__icontains=search)
            | Q(nbok_category__l1__icontains=search)
            | Q(nbok_category__l2__icontains=search)
            | Q(nbok_category__l3__icontains=search)
            | Q(nbok_category__l4__icontains=search)
            | Q(nbok_category__l5__icontains=search)
            | Q(nbok_category__l6__icontains=search)
        ).distinct()
    if nbok_row_id and nbok_level:
        queryset = _nbok_filter(queryset, row_id=nbok_row_id, level=nbok_level)
    elif category_id:
        # Backward compatibility for old bookmarks/API callers.
        categories = categories_with_parents()
        queryset = queryset.filter(category_id__in=category_descendant_ids(categories, category_id))
    if availability == "available":
        queryset = queryset.filter(physical_count__gt=0, physical_available__gt=0)
    elif availability == "borrowed":
        queryset = queryset.filter(physical_count__gt=0, physical_available__lt=F("physical_count"))
    return queryset


def book_detail_queryset():
    return base_book_queryset()


def approved_comments(book):
    approved_replies = BookComment.objects.filter(is_approved=True).order_by("created_at")
    return (
        BookComment.objects.filter(book=book, parent__isnull=True, is_approved=True)
        .prefetch_related(Prefetch("replies", queryset=approved_replies))
        .order_by("-created_at")
    )


def category_direct_counts() -> dict[int | None, int]:
    return dict(Book.objects.values_list("category_id").annotate(total=Count("id")))
