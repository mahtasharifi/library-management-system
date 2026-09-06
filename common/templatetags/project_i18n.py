"""Template access to the project localization provider."""

from django import template

from common.i18n import translate

register = template.Library()


@register.simple_tag
def t(key: str, **params) -> str:
    return translate(key, **params)
