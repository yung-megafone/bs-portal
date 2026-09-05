from django import template

from apps.core.version import __version__

register = template.Library()


@register.simple_tag
def portal_version():
    return __version__
