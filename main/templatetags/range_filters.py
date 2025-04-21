from django import template
register = template.Library()

@register.filter
def get_range(start, end):
    return range(int(start), int(end) + 1)

