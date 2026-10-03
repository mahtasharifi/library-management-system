"""Read-only browser localization endpoint."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from common.i18n import translation_bundle


@require_GET
def translations(request, scope: str):
    if scope not in {"library", "admin", "upload", "site", "notifications"}:
        return JsonResponse({"detail": "unknown_translation_scope"}, status=404)
    return JsonResponse({"language": "fa-ir", "translations": translation_bundle(scope)})
