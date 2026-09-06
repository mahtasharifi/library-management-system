"""NBOK taxonomy helpers used by the administrative category UI."""

from __future__ import annotations

from collections import Counter

from django.core.exceptions import ValidationError

from common.i18n import translate as t

from ..models import Book, NBOKEntry

LEVELS = ("L1", "L2", "L3", "L4", "L5", "L6")
FIELD_BY_LEVEL = {level: level.lower() for level in LEVELS}


def clean_text(value) -> str:
    return " ".join(str(value or "").replace("\u200b", "").split()).strip()


def entry_path_map(entry: NBOKEntry, upto_level: str | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    for level in LEVELS:
        value = clean_text(getattr(entry, FIELD_BY_LEVEL[level], ""))
        if value:
            result[level] = value
        if upto_level == level:
            break
    return result


def path_text(path_map: dict[str, str]) -> str:
    return " / ".join(path_map[level] for level in LEVELS if path_map.get(level))


def selection(entry: NBOKEntry | None, level: str | None) -> dict | None:
    level = clean_text(level).upper()
    if not entry or level not in LEVELS:
        return None
    value = clean_text(getattr(entry, FIELD_BY_LEVEL[level], ""))
    if not value:
        return None
    path_map = entry_path_map(entry, level)
    return {
        "row_id": entry.id,
        "level": level,
        "name": value,
        "path": path_map,
        "path_text": path_text(path_map),
        "key": node_key(path_map, level),
    }


def node_key(path_map: dict[str, str], level: str) -> str:
    parts = [clean_text(path_map.get(item)) for item in LEVELS[: LEVELS.index(level) + 1]]
    return f"{level}:" + "\x1f".join(parts)


def _book_count_by_node() -> Counter:
    counts: Counter = Counter()
    books = Book.objects.select_related("nbok_category").exclude(nbok_category__isnull=True)
    for book in books.only("id", "nbok_category_id", "nbok_category_level", "nbok_category__id", *[f"nbok_category__{f}" for f in FIELD_BY_LEVEL.values()]):
        picked = selection(book.nbok_category, book.nbok_category_level)
        if picked:
            counts[picked["key"]] += 1
    return counts


def tree() -> list[dict]:
    """Return unique conceptual L1..L6 nodes derived from the row-oriented NBOK table."""
    entries = list(NBOKEntry.objects.all().order_by("id"))
    nodes: dict[str, dict] = {}
    roots: list[dict] = []

    for entry in entries:
        path_map: dict[str, str] = {}
        parent = None
        for depth, level in enumerate(LEVELS):
            value = clean_text(getattr(entry, FIELD_BY_LEVEL[level], ""))
            if not value:
                continue
            path_map[level] = value
            key = node_key(path_map, level)
            node = nodes.get(key)
            if node is None:
                node = {
                    "id": key,
                    "row_id": entry.id,
                    "level_code": level,
                    "level": depth,
                    "name": value,
                    "path": dict(path_map),
                    "path_text": path_text(path_map),
                    "book_count": 0,
                    "children": [],
                }
                nodes[key] = node
                if parent is None:
                    roots.append(node)
                else:
                    parent["children"].append(node)
            elif entry.id < node["row_id"]:
                node["row_id"] = entry.id
            parent = node

    direct_counts = _book_count_by_node()

    def aggregate(node: dict) -> int:
        direct = direct_counts.get(node["id"], 0)
        descendant = sum(aggregate(child) for child in node["children"])
        node["book_count"] = direct + descendant
        return node["book_count"]

    for root in roots:
        aggregate(root)
    return roots


def directly_used_nodes() -> list[dict]:
    """Return only NBOK nodes that books are explicitly assigned to.

    Parent/ancestor nodes are intentionally not promoted just because a book is
    assigned to one of their descendants.  The public catalog therefore shows
    exactly the category level selected by an administrator for each book.
    """
    direct_counts = _book_count_by_node()
    result: list[dict] = []

    def walk(items: list[dict]) -> None:
        for node in items:
            direct = int(direct_counts.get(node["id"], 0) or 0)
            if direct > 0:
                result.append({
                    **node,
                    "book_count": direct,
                    "children": [],
                })
            walk(node.get("children", []))

    walk(tree())
    return result


def resolve_selection(row_id, level) -> tuple[NBOKEntry | None, str | None]:
    if row_id in (None, ""):
        return None, None
    level = clean_text(level).upper()
    if level not in LEVELS:
        raise ValidationError(t("admin.nbok.invalid_selection"))
    try:
        row_id = int(row_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError(t("admin.nbok.invalid_selection")) from exc
    entry = NBOKEntry.objects.filter(id=row_id).first()
    if entry is None or not clean_text(getattr(entry, FIELD_BY_LEVEL[level], "")):
        raise ValidationError(t("admin.nbok.invalid_selection"))
    return entry, level


def create_category(*, name: str, parent_row_id=None, parent_level=None) -> NBOKEntry:
    name = clean_text(name)
    if not name:
        raise ValidationError(t("admin.nbok.name_required"))
    if len(name) > 255:
        raise ValidationError(t("admin.nbok.name_too_long"))

    values = {field: None for field in FIELD_BY_LEVEL.values()}
    if parent_row_id in (None, ""):
        target_level = "L1"
    else:
        parent, parent_level = resolve_selection(parent_row_id, parent_level)
        index = LEVELS.index(parent_level)
        if index >= len(LEVELS) - 1:
            raise ValidationError(t("admin.nbok.max_depth"))
        parent_path = entry_path_map(parent, parent_level)
        for level, value in parent_path.items():
            values[FIELD_BY_LEVEL[level]] = value
        target_level = LEVELS[index + 1]

    values[FIELD_BY_LEVEL[target_level]] = name
    levels_to_compare = LEVELS[: LEVELS.index(target_level) + 1]
    for existing in NBOKEntry.objects.all().only(*[FIELD_BY_LEVEL[level] for level in levels_to_compare]):
        if all(
            clean_text(getattr(existing, FIELD_BY_LEVEL[level], ""))
            == clean_text(values[FIELD_BY_LEVEL[level]])
            for level in levels_to_compare
        ):
            raise ValidationError(t("admin.nbok.exists"))
    return NBOKEntry.objects.create(**values)
