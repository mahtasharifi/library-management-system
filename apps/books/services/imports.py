"""Validated and transactional physical-book spreadsheet imports."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import openpyxl
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction

from common.i18n import translate as t

from ..models import Book, Category

MAX_XLSX_SIZE = 10 * 1024 * 1024
MAX_UNCOMPRESSED_XLSX_SIZE = 50 * 1024 * 1024
MAX_XLSX_MEMBERS = 500
MAX_IMPORT_ROWS = 2000
MAX_TAGS = 50

from ..import_schema import HEADER_MAP


@dataclass(frozen=True)
class ImportResult:
    success_count: int
    errors: list[str]


def _read_all(uploaded) -> bytes:
    if uploaded.size <= 0 or uploaded.size > MAX_XLSX_SIZE:
        raise ValidationError(t("books.import.validation.file_size"))
    if Path(uploaded.name).suffix.lower() != ".xlsx":
        raise ValidationError(t("books.import.validation.xlsx_only"))
    position = uploaded.tell()
    uploaded.seek(0)
    data = uploaded.read(MAX_XLSX_SIZE + 1)
    uploaded.seek(position)
    if len(data) > MAX_XLSX_SIZE or not data.startswith(b"PK\x03\x04"):
        raise ValidationError(t("books.import.validation.xlsx_structure"))
    return data


def _validate_zip_budget(data: bytes) -> None:
    try:
        with ZipFile(BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > MAX_XLSX_MEMBERS:
                raise ValidationError(t("books.import.validation.too_complex"))
            total = sum(member.file_size for member in members)
            if total > MAX_UNCOMPRESSED_XLSX_SIZE:
                raise ValidationError(t("books.import.validation.uncompressed_size"))
    except BadZipFile as exc:
        raise ValidationError(t("books.import.validation.xlsx_invalid")) from exc


def rows_from_xlsx(uploaded) -> list[dict]:
    data = _read_all(uploaded)
    _validate_zip_budget(data)
    try:
        workbook = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
        sheet = workbook.active
        iterator = sheet.iter_rows(values_only=True)
        first = next(iterator, None)
        if not first:
            raise ValidationError(t("books.import.validation.empty"))
        raw_headers = [str(value or "").strip() for value in first]
        keys = [HEADER_MAP.get(header) for header in raw_headers]
        if "title" not in keys or "author" not in keys:
            raise ValidationError(t("books.import.validation.required_columns"))
        rows: list[dict] = []
        for index, values in enumerate(iterator, start=1):
            if index > MAX_IMPORT_ROWS:
                raise ValidationError(t("books.import.validation.max_file_rows", count=MAX_IMPORT_ROWS))
            rows.append({key: values[column] for column, key in enumerate(keys) if key})
        return rows
    except ValidationError:
        raise
    except (ValueError, TypeError, OSError, KeyError) as exc:
        raise ValidationError(t("books.import.validation.read_failed")) from exc



def normalize_import_rows(rows: list) -> list:
    """Normalize JSON import keys to the same internal schema used by XLSX imports."""
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            normalized.append(row)
            continue
        normalized.append({HEADER_MAP.get(str(key).strip(), str(key).strip()): value for key, value in row.items()})
    return normalized

def _clean_text(value, max_length: int, label: str, *, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValidationError(t("books.import.validation.required_field", label=label))
    if len(text) > max_length:
        raise ValidationError(t("books.import.validation.text_too_long", label=label))
    return text


def _clean_count(value) -> int:
    try:
        count = int(value or 1)
    except (TypeError, ValueError) as exc:
        raise ValidationError(t("books.import.validation.count_integer")) from exc
    if not 1 <= count <= 10000:
        raise ValidationError(t("books.import.validation.count_range"))
    return count


def _clean_cover_url(value) -> str:
    url = _clean_text(value, 1000, t("books.import.label.cover_url"))
    if url:
        URLValidator(schemes=["https"])(url)
    return url


def _clean_tags(value) -> list[str]:
    tags = [tag.strip() for tag in str(value or "").replace(",", "،").split("،") if tag.strip()]
    if len(tags) > MAX_TAGS or any(len(tag) > 100 for tag in tags):
        raise ValidationError(t("books.import.validation.tags_limit"))
    return tags


def _clean_row(row: dict, number: int) -> tuple[dict | None, str | None]:
    if not any(value not in (None, "") for value in row.values()):
        return None, None
    try:
        cleaned = {
            "title": _clean_text(row.get("title"), 255, t("books.book.field.title"), required=True),
            "author": _clean_text(row.get("author"), 255, t("common.labels.author"), required=True),
            "translator": _clean_text(row.get("translator"), 255, t("common.labels.translator")) or None,
            "publisher": _clean_text(row.get("publisher"), 255, t("common.labels.publisher")) or None,
            "library": _clean_text(row.get("library"), 255, t("books.book.field.library")) or None,
            "category_path": _clean_text(row.get("category"), 500, t("books.category.model.single")),
            "summary": _clean_text(row.get("summary"), 20000, t("books.book.field.summary")) or None,
            "physical_count": _clean_count(row.get("physical_count")),
            "physical_location": _clean_text(row.get("physical_location"), 200, t("books.book.field.physical_location")) or None,
            "cover_url": _clean_cover_url(row.get("cover_url")) or None,
            "tags": _clean_tags(row.get("tags")),
        }
        return cleaned, None
    except ValidationError as exc:
        return None, t("books.import.validation.row_error", number=number, error="; ".join(exc.messages))


def _find_or_create_category(path: str) -> Category | None:
    parent = None
    parts = [part.strip() for part in path.replace(">", "/").split("/") if part.strip()]
    for name in parts:
        category = Category.objects.filter(name=name, parent=parent).first()
        parent = category or Category.objects.create(name=name, parent=parent)
    return parent


def import_physical_rows(rows: list[dict]) -> ImportResult:
    if len(rows) > MAX_IMPORT_ROWS:
        return ImportResult(0, [t("books.import.validation.max_batch_rows", count=MAX_IMPORT_ROWS)])
    cleaned_rows: list[dict] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for number, row in enumerate(rows, start=2):
        if not isinstance(row, dict):
            errors.append(t("books.import.validation.row_structure", number=number))
            continue
        cleaned, error = _clean_row(row, number)
        if error:
            errors.append(error)
            continue
        if cleaned is None:
            continue
        key = (cleaned["title"].casefold(), cleaned["author"].casefold())
        if key in seen or Book.objects.filter(title__iexact=cleaned["title"], author__iexact=cleaned["author"]).exists():
            errors.append(t("books.import.validation.duplicate_book", number=number, title=cleaned["title"]))
            continue
        seen.add(key)
        cleaned_rows.append(cleaned)
    if errors:
        return ImportResult(0, errors[:50])

    with transaction.atomic():
        for data in cleaned_rows:
            tags = data.pop("tags")
            category_path = data.pop("category_path")
            count = data["physical_count"]
            book = Book.objects.create(
                category=_find_or_create_category(category_path),
                physical_available=count,
                **data,
            )
            book.tags = tags
            book.save(update_fields=["tags"])
    return ImportResult(len(cleaned_rows), [])
