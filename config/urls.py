"""Root URL configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from common import health, i18n_views, metrics


def home_redirect(request):
    if request.user.is_authenticated:
        return redirect("/library/")

    return redirect("accounts:login")


urlpatterns = [
    path("health/", health.health, name="health"),
    path("ready/", health.ready, name="ready"),
    path("live/", health.live, name="live"),
    path("metrics/", metrics.metrics, name="metrics"),

    path(
        "api/v1/translations/<slug:scope>/",
        i18n_views.translations,
        name="ui_translations",
    ),

    path("admin/", admin.site.urls),

    path("", home_redirect, name="home"),

    path(
        "accounts/",
        include("apps.accounts.urls", namespace="accounts"),
    ),

    path(
        "library/",
        include("apps.books.urls"),
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )