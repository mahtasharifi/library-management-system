"""TOTP multi-factor authentication helpers."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import io
import secrets
import struct
import time
from dataclasses import dataclass
from urllib.parse import quote, urlencode

import qrcode
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from .models import MfaCredential

TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6
TOTP_WINDOW = 1
RECOVERY_CODE_COUNT = 10
RECOVERY_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


@dataclass(frozen=True)
class VerificationResult:
    accepted: bool
    used_recovery_code: bool = False


def _fernets() -> list[Fernet]:
    configured = list(getattr(settings, "MFA_ENCRYPTION_KEYS", []) or [])
    if not configured:
        legacy = str(getattr(settings, "MFA_ENCRYPTION_KEY", "") or "").strip()
        if legacy:
            configured = [legacy]
    if not configured:
        raise ImproperlyConfigured("MFA_ENCRYPTION_KEYS is required for MFA operations.")
    fernets: list[Fernet] = []
    try:
        for value in configured:
            fernets.append(Fernet(str(value).strip().encode("ascii")))
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ImproperlyConfigured("Every MFA_ENCRYPTION_KEYS entry must be a valid Fernet key.") from exc
    return fernets


def generate_encryption_key() -> str:
    return Fernet.generate_key().decode("ascii")


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def encrypt_secret(secret: str) -> str:
    return _fernets()[0].encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_secret(encrypted_secret: str) -> str:
    payload = encrypted_secret.encode("ascii")
    for fernet in _fernets():
        try:
            return fernet.decrypt(payload).decode("ascii")
        except InvalidToken:
            continue
        except (ValueError, UnicodeError) as exc:
            raise ImproperlyConfigured("Stored MFA secret is malformed.") from exc
    raise ImproperlyConfigured("Stored MFA secret cannot be decrypted with the configured key ring.")


def _decode_base32(secret: str) -> bytes:
    normalized = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    try:
        return base64.b32decode(normalized + padding, casefold=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid TOTP secret") from exc


def totp_code(secret: str, *, counter: int | None = None, at_time: int | float | None = None) -> str:
    if counter is None:
        timestamp = time.time() if at_time is None else at_time
        counter = int(timestamp // TOTP_PERIOD_SECONDS)
    digest = hmac.new(_decode_base32(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % (10 ** TOTP_DIGITS):0{TOTP_DIGITS}d}"


def matching_counter(secret: str, code: str, *, now: int | float | None = None) -> int | None:
    if not (code.isdigit() and len(code) == TOTP_DIGITS):
        return None
    current = int((time.time() if now is None else now) // TOTP_PERIOD_SECONDS)
    for delta in range(-TOTP_WINDOW, TOTP_WINDOW + 1):
        candidate = current + delta
        if candidate >= 0 and hmac.compare_digest(totp_code(secret, counter=candidate), code):
            return candidate
    return None


def is_mfa_required(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    return bool(getattr(settings, "MFA_REQUIRED_FOR_ALL", False))


def get_credential(user) -> MfaCredential:
    return MfaCredential.objects.get_or_create(user=user)[0]


def start_enrollment(user) -> tuple[MfaCredential, str]:
    """Create a fresh encrypted pending secret and invalidate earlier MFA sessions."""
    secret = generate_totp_secret()
    with transaction.atomic():
        credential, _ = MfaCredential.objects.select_for_update().get_or_create(user=user)
        credential.encrypted_secret = encrypt_secret(secret)
        credential.is_enabled = False
        credential.last_counter = None
        credential.recovery_code_hashes = []
        credential.version += 1
        credential.verified_at = None
        credential.save()
    return credential, secret


def pending_secret(user) -> str | None:
    credential = MfaCredential.objects.filter(user=user, is_enabled=False).first()
    if not credential or not credential.encrypted_secret:
        return None
    return decrypt_secret(credential.encrypted_secret)


def _new_recovery_codes() -> list[str]:
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(12))
        codes.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:]}")
    return codes


def _normalize_recovery_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def enable_enrollment(user, code: str) -> list[str] | None:
    """Verify the first TOTP and return plaintext recovery codes exactly once."""
    with transaction.atomic():
        credential = MfaCredential.objects.select_for_update().filter(user=user).first()
        if not credential or credential.is_enabled or not credential.encrypted_secret:
            return None
        secret = decrypt_secret(credential.encrypted_secret)
        counter = matching_counter(secret, code)
        if counter is None:
            return None
        recovery_codes = _new_recovery_codes()
        credential.is_enabled = True
        credential.last_counter = counter
        credential.recovery_code_hashes = [make_password(_normalize_recovery_code(item)) for item in recovery_codes]
        credential.verified_at = timezone.now()
        credential.save(update_fields=[
            "is_enabled", "last_counter", "recovery_code_hashes", "verified_at", "updated_at",
        ])
        return recovery_codes


def verify_second_factor(user, code: str) -> VerificationResult:
    """Atomically verify TOTP/recovery input and prevent TOTP replay."""
    normalized = code.strip()
    with transaction.atomic():
        credential = MfaCredential.objects.select_for_update().filter(user=user, is_enabled=True).first()
        if not credential or not credential.encrypted_secret:
            return VerificationResult(False)

        if normalized.isdigit() and len(normalized) == TOTP_DIGITS:
            secret = decrypt_secret(credential.encrypted_secret)
            counter = matching_counter(secret, normalized)
            if counter is None or (credential.last_counter is not None and counter <= credential.last_counter):
                return VerificationResult(False)
            credential.last_counter = counter
            credential.save(update_fields=["last_counter", "updated_at"])
            return VerificationResult(True)

        recovery = _normalize_recovery_code(normalized)
        if len(recovery) != 12:
            return VerificationResult(False)
        hashes = list(credential.recovery_code_hashes or [])
        for index, stored_hash in enumerate(hashes):
            if check_password(recovery, stored_hash):
                del hashes[index]
                credential.recovery_code_hashes = hashes
                credential.save(update_fields=["recovery_code_hashes", "updated_at"])
                return VerificationResult(True, used_recovery_code=True)
    return VerificationResult(False)


def regenerate_recovery_codes(user) -> list[str]:
    recovery_codes = _new_recovery_codes()
    with transaction.atomic():
        credential = MfaCredential.objects.select_for_update().get(user=user, is_enabled=True)
        credential.recovery_code_hashes = [make_password(_normalize_recovery_code(item)) for item in recovery_codes]
        credential.version += 1
        credential.save(update_fields=["recovery_code_hashes", "version", "updated_at"])
    return recovery_codes


def reset_mfa(user) -> None:
    """Disable MFA and bump the version so existing MFA-authenticated sessions fail closed."""
    with transaction.atomic():
        credential, _ = MfaCredential.objects.select_for_update().get_or_create(user=user)
        credential.encrypted_secret = ""
        credential.is_enabled = False
        credential.last_counter = None
        credential.recovery_code_hashes = []
        credential.verified_at = None
        credential.version += 1
        credential.save()


def provisioning_uri(user, secret: str) -> str:
    issuer = str(getattr(settings, "MFA_ISSUER", "Library"))
    account = user.email or user.username
    label = f"{issuer}:{account}"
    query = urlencode({"secret": secret, "issuer": issuer, "algorithm": "SHA1", "digits": 6, "period": 30})
    return f"otpauth://totp/{quote(label)}?{query}"


def qr_data_uri(user, secret: str) -> str:
    image = qrcode.make(provisioning_uri(user, secret))
    output = io.BytesIO()
    image.save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
