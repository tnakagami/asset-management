from django import template

register = template.Library()

@register.filter
def get_value(_dict, key):
  return _dict[key] if key in _dict.keys() else None
