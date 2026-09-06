"""Public interface for books HTTP views."""

from .public import (
    api_books,
    api_categories,
    api_comments,
    api_comments_list,
    api_comments_reply,
    api_contact,
    api_rate_book,
    api_request_book,
    api_request_physical_book,
    book_catalog,
    book_detail,
    book_pdf_download,
    dashboard,
    index,
    upload_view,
)
from .admin import *  # noqa: F401,F403 - URL compatibility exports staff endpoints.

__all__ = [name for name in globals() if not name.startswith("_")]
