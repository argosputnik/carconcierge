from django import template

register = template.Library()

@register.filter
def get_field(obj, name):
    return getattr(obj, name, '')


