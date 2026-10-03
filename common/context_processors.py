"""Global template context kept intentionally small."""

from django.conf import settings
from common.i18n import translate as t


def application_context(request):
    return {
        "application_name": t("app.name"),
        "site_url": settings.SITE_URL,
    }
