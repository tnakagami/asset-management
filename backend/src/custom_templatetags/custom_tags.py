from django import template
from django.urls import reverse_lazy
register = template.Library()

@register.filter(name='is_login_page')
def is_login_page(request):
  login_url = reverse_lazy('account:login')
  target_url = request.path
  
  return login_url == target_url