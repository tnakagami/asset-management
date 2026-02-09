import pytest
from django.urls import reverse
from custom_templatetags import custom_tags
from dataclasses import dataclass

@dataclass
class _CustomRequest:
  path: str

@pytest.mark.customtag
@pytest.mark.parametrize([
  'target_path',
  'is_login_page',
], [
  ('', True),
  ('/dummy', False),
], ids=['valid-login-path', 'invalid-login-path'])
def test_login_page(target_path, is_login_page):
  base_path = reverse('account:login')
  request = _CustomRequest(path=f'{base_path}{target_path}')
  judge = custom_tags.is_login_page(request)

  assert judge == is_login_page
