from django.apps import AppConfig
from common.i18n import translate as t


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    label = 'accounts'
    verbose_name = t("accounts.app.verbose_name")
