from django import template
from decimal import Decimal

register = template.Library()

@register.simple_tag
def url_replace(request, field, value):
  url_dict = request.GET.copy()
  url_dict[field] = str(value)

  return url_dict.urlencode()

@register.filter()
def get_total_diff(instance):
  stock_price = instance.stock.price
  purchased_stock_value = instance.price
  diff = (stock_price - purchased_stock_value) * instance.count

  return diff

@register.filter()
def is_negative(value):
  ret = value < 0

  return ret

@register.filter()
def get_yield(instance):
  dividend = instance.stock.dividend
  price = instance.stock.price

  try:
    _yield = dividend / price * Decimal('100.0')
  except ZeroDivisionError:
    _yield = 0

  return _yield

@register.filter()
def get_multi_per_pbr(instance):
  per = instance.stock.per
  pbr = instance.stock.pbr
  ret = per * pbr

  return ret