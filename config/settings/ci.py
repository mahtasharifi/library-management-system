"""CI settings: Production security/database behavior with local non-delivery email."""

import os

if os.getenv("CI", "").lower() not in {"1", "true", "yes"}:
    raise RuntimeError("config.settings.ci is only for CI validation.")

from .production import *  # noqa: F403,E402

# CI must not contact a real SMTP provider. All other Production validation,
# including MySQL, HTTPS/security settings and external storage paths, remains active.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SECURE_HSTS_PRELOAD = True
