import pytest
from utils.templatetags import utils_extras
from dataclasses import dataclass
from django.utils.http import urlencode

@dataclass
class _CustomGET(dict):
  def __init__(self, init=None):
    self.data = init if init else {}

  def copy(self):
    instance = _CustomGET(init=self.data)

    return instance

  def __setitem__(self, key, value):
    if not isinstance(key, str):
      raise Exception()

    self.data[key] = value

  def urlencode(self):
    return urlencode(self.data)

@dataclass
class _CustomRequest:
  GET: _CustomGET

@pytest.mark.customtag
def test_url_replace():
  instance = _CustomGET(init={'page': 'aaa'})
  request = _CustomRequest(GET=instance)
  output = utils_extras.url_replace(request, 'next', 'bbb')
  exact = urlencode({'page': 'aaa', 'next': 'bbb'})

  assert output == exact