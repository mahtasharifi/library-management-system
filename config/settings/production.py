"""Production settings. All credentials are supplied by the environment."""

from django.core.exceptions import ImproperlyConfigured

from common.env import env, env_bool, env_int, env_list, required_env
from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = required_env("DJANGO_SECRET_KEY")
MFA_ENCRYPTION_KEYS = env_list("MFA_ENCRYPTION_KEYS")
if not MFA_ENCRYPTION_KEYS:
    legacy_mfa_key = env("MFA_ENCRYPTION_KEY")
    if legacy_mfa_key:
        MFA_ENCRYPTION_KEYS = [legacy_mfa_key]
    else:
        raise ImproperlyConfigured("MFA_ENCRYPTION_KEYS is required in production.")
MFA_ENCRYPTION_KEY = MFA_ENCRYPTION_KEYS[0]
MFA_REQUIRED_FOR_ALL = env_bool("MFA_REQUIRED_FOR_ALL", False)
MFA_ENFORCEMENT_ENABLED = env_bool("MFA_ENFORCEMENT_ENABLED", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must contain explicit production hosts.")


def _outside_source_path(name: str) -> Path:
    value = Path(required_env(name)).expanduser()
    if not value.is_absolute():
        raise ImproperlyConfigured(f"{name} must be an absolute path in production.")
    resolved = value.resolve()
    source_root = BASE_DIR.resolve()  # noqa: F405
    if resolved == source_root or source_root in resolved.parents:
        raise ImproperlyConfigured(f"{name} must be outside the application source tree.")
    return resolved


# Runtime/user-generated files must never live inside the source tree in Production.
MEDIA_ROOT = _outside_source_path("MEDIA_ROOT")

DJANGO_MIGRATION_MODE = env_bool("DJANGO_MIGRATION_MODE", False)
database_user = required_env("DB_MIGRATION_USER") if DJANGO_MIGRATION_MODE else required_env("DB_USER")
database_password = required_env("DB_MIGRATION_PASSWORD") if DJANGO_MIGRATION_MODE else required_env("DB_PASSWORD")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": required_env("DB_NAME"),
        "USER": database_user,
        "PASSWORD": database_password,
        "HOST": required_env("DB_HOST"),
        "PORT": env("DB_PORT", "3306"),
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
        "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
    }
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = required_env("EMAIL_HOST")
EMAIL_PORT = env_int("EMAIL_PORT", 465)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", True)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_HOST_USER = required_env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = required_env("EMAIL_HOST_PASSWORD")
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 15)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

if LIBRARY_CDN_STORAGE == "filesystem":  # noqa: F405
    LIBRARY_CDN_ROOT = _outside_source_path("LIBRARY_CDN_ROOT")
elif LIBRARY_CDN_STORAGE == "ftp":  # noqa: F405
    LIBRARY_CDN_FTP_HOST = required_env("LIBRARY_CDN_FTP_HOST")
    LIBRARY_CDN_FTP_USER = required_env("LIBRARY_CDN_FTP_USER")
    LIBRARY_CDN_FTP_PASSWORD = required_env("LIBRARY_CDN_FTP_PASSWORD")
    LIBRARY_CDN_FTP_ROOT = required_env("LIBRARY_CDN_FTP_ROOT")
    if not LIBRARY_CDN_FTP_TLS:  # noqa: F405
        raise ImproperlyConfigured("Production FTP storage requires LIBRARY_CDN_FTP_TLS=true.")
    if not str(LIBRARY_CDN_BASE_URL).startswith("https://"):  # noqa: F405
        raise ImproperlyConfigured("LIBRARY_CDN_BASE_URL must use HTTPS in production.")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# Fail closed when any configured MFA encryption key is malformed. The first
# key is the active encryption key; remaining keys are decrypt-only during rotation.
try:
    from cryptography.fernet import Fernet
    for mfa_key in MFA_ENCRYPTION_KEYS:
        Fernet(mfa_key.encode("ascii"))
except (ValueError, TypeError) as exc:
    raise ImproperlyConfigured("Every MFA_ENCRYPTION_KEYS entry must be a valid Fernet key.") from exc

BACKGROUND_JOBS_EAGER = env_bool("BACKGROUND_JOBS_EAGER", True)
CSRF_COOKIE_HTTPONLY = True
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", True)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}

if EMAIL_USE_SSL and EMAIL_USE_TLS:
    raise ImproperlyConfigured("EMAIL_USE_SSL and EMAIL_USE_TLS cannot both be true.")
if not SITE_URL.startswith("https://"):  # noqa: F405
    raise ImproperlyConfigured("SITE_URL must use HTTPS in production.")
if any(host.strip() == "*" for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Wildcard production ALLOWED_HOSTS is forbidden.")
if any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):  # noqa: F405
    raise ImproperlyConfigured("Production CSRF_TRUSTED_ORIGINS must use HTTPS.")
