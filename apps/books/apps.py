from django.apps import AppConfig
from common.i18n import translate as t


class BooksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.books'
    label = 'books'
    verbose_name = t("books.app.verbose_name")
