"""Shared Django settings for the Library application."""

from pathlib import Path

from common.env import env, env_bool, env_int, env_list

BASE_DIR = Path(__file__).resolve().parents[2]

DEBUG = False
SECRET_KEY = ""
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "common.apps.CommonConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.books.apps.BooksConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "common.middleware.CorrelationIdMiddleware",
    "common.middleware.RequestMetricsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "common.middleware.MfaEnforcementMiddleware",
    "common.middleware.AdminAuditMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.ContentSecurityPolicyMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "common.context_processors.application_context",
            ],
        },
    }
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fa-ir"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 24 * 7)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/library/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

SITE_URL = env("SITE_URL", "http://127.0.0.1:8000")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "library@localhost")
SERVER_EMAIL = env("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

LIBRARY_CDN_STORAGE = env("LIBRARY_CDN_STORAGE", "filesystem")
LIBRARY_CDN_BASE_URL = env("LIBRARY_CDN_BASE_URL", "/media/library_cdn/")
LIBRARY_CDN_ROOT = Path(env("LIBRARY_CDN_ROOT", str(MEDIA_ROOT / "library_cdn")))
LIBRARY_CDN_FTP_HOST = env("LIBRARY_CDN_FTP_HOST", "")
LIBRARY_CDN_FTP_PORT = env_int("LIBRARY_CDN_FTP_PORT", 21)
LIBRARY_CDN_FTP_USER = env("LIBRARY_CDN_FTP_USER", "")
LIBRARY_CDN_FTP_PASSWORD = env("LIBRARY_CDN_FTP_PASSWORD", "")
LIBRARY_CDN_FTP_ROOT = env("LIBRARY_CDN_FTP_ROOT", "")
LIBRARY_CDN_FTP_TLS = env_bool("LIBRARY_CDN_FTP_TLS", True)
LIBRARY_CDN_FTP_PASSIVE = env_bool("LIBRARY_CDN_FTP_PASSIVE", True)
LIBRARY_CDN_FTP_TIMEOUT = env_int("LIBRARY_CDN_FTP_TIMEOUT", 30)

MFA_ISSUER = env("MFA_ISSUER", "Library")
MFA_ENCRYPTION_KEY = env("MFA_ENCRYPTION_KEY", "")
MFA_ENCRYPTION_KEYS = env_list("MFA_ENCRYPTION_KEYS")
if not MFA_ENCRYPTION_KEYS and MFA_ENCRYPTION_KEY:
    MFA_ENCRYPTION_KEYS = [MFA_ENCRYPTION_KEY]
if MFA_ENCRYPTION_KEYS:
    # Compatibility alias; new encryption always uses the first key.
    MFA_ENCRYPTION_KEY = MFA_ENCRYPTION_KEYS[0]
MFA_REQUIRED_FOR_ALL = env_bool("MFA_REQUIRED_FOR_ALL", False)
MFA_ENFORCEMENT_ENABLED = env_bool("MFA_ENFORCEMENT_ENABLED", True)

CONTENT_SECURITY_POLICY = env(
    "CONTENT_SECURITY_POLICY",
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; style-src-attr 'unsafe-inline'; "
    "img-src 'self' data: https:; font-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'",
)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# Explicit trusted origins only; wildcard origins are never created here.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", False)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "library",
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "common.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "security": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

HEALTH_CHECK_DETAILS = env_bool("HEALTH_CHECK_DETAILS", False)

# Background jobs are synchronous only in explicit development/test settings.
BACKGROUND_JOBS_EAGER = env_bool("BACKGROUND_JOBS_EAGER", False)
BACKGROUND_WORKER_MAX_AGE_SECONDS = env_int("BACKGROUND_WORKER_MAX_AGE_SECONDS", 120)
BACKGROUND_JOB_LOCK_TIMEOUT_SECONDS = env_int("BACKGROUND_JOB_LOCK_TIMEOUT_SECONDS", 3600)
BACKGROUND_JOB_RETENTION_DAYS = env_int("BACKGROUND_JOB_RETENTION_DAYS", 30)

# Bound request parsing independently of per-file validators.
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("DATA_UPLOAD_MAX_MEMORY_SIZE", 12 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = env_int("FILE_UPLOAD_MAX_MEMORY_SIZE", 5 * 1024 * 1024)
DATA_UPLOAD_MAX_NUMBER_FIELDS = env_int("DATA_UPLOAD_MAX_NUMBER_FIELDS", 2000)

# Optional protected operational metrics endpoint.
METRICS_TOKEN = env("METRICS_TOKEN", "")
