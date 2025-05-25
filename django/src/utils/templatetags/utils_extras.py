from django import template

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