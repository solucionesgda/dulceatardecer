from django import template

from institucional.moneda import formatear_moneda

register = template.Library()


@register.filter
def moneda(valor):
    return formatear_moneda(valor)
