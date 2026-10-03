"""Isolated SQLite settings for the automated test suite."""

import secrets
from pathlib import Path
from cryptography.fernet import Fernet

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = secrets.token_urlsafe(32)
MFA_ENCRYPTION_KEY = Fernet.generate_key().decode("ascii")
MFA_ENCRYPTION_KEYS = [MFA_ENCRYPTION_KEY]
MFA_REQUIRED_FOR_ALL = False
MFA_ENFORCEMENT_ENABLED = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "library-test@localhost"
LIBRARY_CDN_STORAGE = "filesystem"
LIBRARY_CDN_ROOT = BASE_DIR / ".test-media" / "library_cdn"  # noqa: F405
LIBRARY_CDN_BASE_URL = "/media/library_cdn/"
MEDIA_ROOT = BASE_DIR / ".test-media"  # noqa: F405
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
BACKGROUND_JOBS_EAGER = True
