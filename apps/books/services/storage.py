"""Validated public CDN storage for library covers and PDF assets."""

from __future__ import annotations

import ftplib
import os
import ssl
import uuid
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage

from common.i18n import translate as t

ASSET_RULES = {
    "cover": {
        "extensions": {".jpg", ".jpeg", ".png", ".webp", ".avif"},
        "content_types": {"image/jpeg", "image/png", "image/webp", "image/avif"},
        "max_size": 5 * 1024 * 1024,
        "folder": "Cover",
    },
    "pdf": {
        "extensions": {".pdf"},
        "content_types": {"application/pdf", "application/x-pdf"},
        "max_size": 100 * 1024 * 1024,
        "folder": "PDF",
    },
}


def _public_url(folder: str, filename: str) -> str:
    base_url = str(settings.LIBRARY_CDN_BASE_URL).rstrip("/") + "/"
    return f"{base_url}{quote(f'{folder}/{filename}', safe='/')}"


def _read_signature(uploaded_file, size: int = 32) -> bytes:
    position = uploaded_file.tell()
    uploaded_file.seek(0)
    signature = uploaded_file.read(size)
    uploaded_file.seek(position)
    return signature


def _signature_matches(asset_type: str, extension: str, signature: bytes) -> bool:
    if asset_type == "pdf":
        return signature.startswith(b"%PDF-")
    if extension in {".jpg", ".jpeg"}:
        return signature.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return signature.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp":
        return signature.startswith(b"RIFF") and signature[8:12] == b"WEBP"
    if extension == ".avif":
        return len(signature) >= 12 and signature[4:8] == b"ftyp" and b"avif" in signature[8:24]
    return False


def validate_library_asset(uploaded_file, asset_type: str) -> tuple[str, dict]:
    rules = ASSET_RULES.get(asset_type)
    if not rules:
        raise ValidationError(t("storage.validation.asset_type"))
    extension = Path(uploaded_file.name).suffix.lower()
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    if extension not in rules["extensions"]:
        raise ValidationError(t("storage.validation.extension"))
    if content_type and content_type not in rules["content_types"]:
        raise ValidationError(t("storage.validation.content_type"))
    if uploaded_file.size <= 0 or uploaded_file.size > rules["max_size"]:
        limit = rules["max_size"] // (1024 * 1024)
        raise ValidationError(t("storage.validation.size", limit=limit))
    if not _signature_matches(asset_type, extension, _read_signature(uploaded_file)):
        raise ValidationError(t("storage.validation.signature"))
    return extension, rules


def _save_on_filesystem(uploaded_file, folder: str, filename: str) -> str:
    root = Path(settings.LIBRARY_CDN_ROOT)
    try:
        root.mkdir(parents=True, exist_ok=True)
        storage = FileSystemStorage(location=str(root))
        saved_name = storage.save(f"{folder}/{filename}", uploaded_file).replace(os.sep, "/")
    except OSError as exc:
        raise ValidationError(t("storage.validation.save_failed")) from exc
    base_url = str(settings.LIBRARY_CDN_BASE_URL).rstrip("/")
    return f"{base_url}/{quote(saved_name, safe='/')}"


def _ftp_client():
    required = (
        settings.LIBRARY_CDN_FTP_HOST,
        settings.LIBRARY_CDN_FTP_USER,
        settings.LIBRARY_CDN_FTP_PASSWORD,
    )
    if not all(required):
        raise ValidationError(t("storage.validation.config_incomplete"))
    ftp = ftplib.FTP_TLS(context=ssl.create_default_context()) if settings.LIBRARY_CDN_FTP_TLS else ftplib.FTP()
    ftp.encoding = "utf-8"
    ftp.connect(settings.LIBRARY_CDN_FTP_HOST, settings.LIBRARY_CDN_FTP_PORT, timeout=settings.LIBRARY_CDN_FTP_TIMEOUT)
    ftp.login(settings.LIBRARY_CDN_FTP_USER, settings.LIBRARY_CDN_FTP_PASSWORD)
    if settings.LIBRARY_CDN_FTP_TLS:
        ftp.prot_p()
    ftp.set_pasv(settings.LIBRARY_CDN_FTP_PASSIVE)
    return ftp


def _ftp_enter_root(ftp) -> None:
    remote_root = str(settings.LIBRARY_CDN_FTP_ROOT).strip("/")
    if not remote_root:
        raise ValidationError(t("storage.validation.root_missing"))
    try:
        for part in PurePosixPath(remote_root).parts:
            if part not in {"/", "", "."}:
                ftp.cwd(part)
    except ftplib.all_errors as exc:
        raise ValidationError(t("storage.validation.path_unavailable")) from exc


def _ftp_enter_upload_folder(ftp, folder: str) -> None:
    _ftp_enter_root(ftp)
    try:
        ftp.cwd(folder)
    except ftplib.error_perm as exc:
        if not str(exc).startswith("550"):
            raise ValidationError(t("storage.validation.path_unavailable")) from exc
        try:
            ftp.mkd(folder)
            ftp.cwd(folder)
        except ftplib.all_errors as inner_exc:
            raise ValidationError(t("storage.validation.path_unavailable")) from inner_exc


def _close_ftp(ftp) -> None:
    if ftp is None:
        return
    try:
        ftp.quit()
    except ftplib.all_errors:
        ftp.close()


def _save_over_ftp(uploaded_file, folder: str, filename: str) -> str:
    ftp = None
    try:
        ftp = _ftp_client()
        _ftp_enter_upload_folder(ftp, folder)
        uploaded_file.seek(0)
        ftp.storbinary(f"STOR {filename}", uploaded_file, blocksize=128 * 1024)
    except ValidationError:
        raise
    except ftplib.all_errors as exc:
        raise ValidationError(t("storage.validation.upload_failed")) from exc
    finally:
        _close_ftp(ftp)
    return _public_url(folder, filename)


def _managed_relative_path(url: str, asset_type: str) -> str | None:
    rules = ASSET_RULES.get(asset_type)
    base_url = str(settings.LIBRARY_CDN_BASE_URL).rstrip("/") + "/"
    value = str(url or "").strip()
    if not rules or not value.startswith(base_url):
        return None
    relative = unquote(value[len(base_url):]).lstrip("/")
    path = PurePosixPath(relative)
    if not relative or ".." in path.parts or path.is_absolute():
        return None
    if len(path.parts) != 2 or path.parts[0] != rules["folder"]:
        return None
    return relative


def is_managed_asset_url(url: str, asset_type: str) -> bool:
    """Return whether a URL belongs to the configured managed CDN folder."""
    return _managed_relative_path(url, asset_type) is not None


def _delete_from_filesystem(relative_path: str) -> None:
    root = Path(settings.LIBRARY_CDN_ROOT).resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValidationError(t("storage.validation.path_unavailable")) from exc
    try:
        candidate.unlink(missing_ok=True)
    except OSError as exc:
        raise ValidationError(t("storage.validation.delete_failed")) from exc


def _delete_over_ftp(relative_path: str) -> None:
    folder, filename = PurePosixPath(relative_path).parts
    ftp = None
    try:
        ftp = _ftp_client()
        _ftp_enter_root(ftp)
        ftp.cwd(folder)
        ftp.delete(filename)
    except ftplib.error_perm as exc:
        if not str(exc).startswith("550"):
            raise ValidationError(t("storage.validation.delete_failed")) from exc
    except ValidationError:
        raise
    except ftplib.all_errors as exc:
        raise ValidationError(t("storage.validation.delete_failed")) from exc
    finally:
        _close_ftp(ftp)


def delete_library_asset(url: str, asset_type: str) -> bool:
    """Delete only assets owned by the configured CDN; ignore external URLs."""
    relative_path = _managed_relative_path(url, asset_type)
    if not relative_path:
        return False
    mode = str(settings.LIBRARY_CDN_STORAGE).strip().lower()
    if mode == "filesystem":
        _delete_from_filesystem(relative_path)
    elif mode == "ftp":
        _delete_over_ftp(relative_path)
    else:
        raise ValidationError(t("storage.validation.not_configured"))
    return True


def save_library_asset(uploaded_file, asset_type: str) -> str:
    extension, rules = validate_library_asset(uploaded_file, asset_type)
    filename = f"{asset_type}-{uuid.uuid4().hex}{extension}"
    mode = str(settings.LIBRARY_CDN_STORAGE).strip().lower()
    if mode == "filesystem":
        return _save_on_filesystem(uploaded_file, rules["folder"], filename)
    if mode == "ftp":
        return _save_over_ftp(uploaded_file, rules["folder"], filename)
    raise ValidationError(t("storage.validation.not_configured"))
