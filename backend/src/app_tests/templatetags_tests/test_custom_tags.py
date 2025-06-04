import pytest
from django.urls import reverse_lazy
from custom_templatetags import custom_tags
from dataclasses import dataclass

@dataclass
class _CustomRequest:
  path: str

@pytest.fixture
def get_login_path():
  return reverse_lazy('account:login')

@pytest.mark.customtag
def test_valid_login_path(get_login_path):
  exact_path = get_login_path
  request = _CustomRequest(path=exact_path)
  judge = custom_tags.is_login_page(request)

  assert judge

@pytest.mark.customtag
def test_invalid_login_path(get_login_path):
  exact_path = get_login_path
  request = _CustomRequest(path=f'{exact_path}/dummy')
  judge = custom_tags.is_login_page(request)

  assert not judge
