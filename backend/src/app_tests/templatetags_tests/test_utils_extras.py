import pytest
from utils.templatetags import utils_extras
from dataclasses import dataclass
from django.utils.http import urlencode
from decimal import Decimal
from app_tests import factories

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
@pytest.mark.django_db
class TestUtilsExtra:
  def test_url_replace(self):
    instance = _CustomGET(init={'page': 'aaa'})
    request = _CustomRequest(GET=instance)
    output = utils_extras.url_replace(request, 'next', 'bbb')
    exact = urlencode({'page': 'aaa', 'next': 'bbb'})

    assert output == exact

  @pytest.mark.parametrize([
    'stock_price',
    'purchased_price',
    'count',
    'exact',
  ], [
    (100, 200, 15, -1500),
    (150, 150, 30, 0),
    (150, 100, 10, 500),
  ], ids=[
    'is-negative-diff',
    'diff-is-zero',
    'is-positive-diff',
  ])
  def test_check_get_total_diff_func(self, stock_price, purchased_price, count, exact):
    user = factories.UserFactory()
    stock = factories.StockFactory(price=stock_price)
    instance = factories.PurchasedStockFactory(
      user=user,
      stock=stock,
      price=purchased_price,
      count=count,
    )
    diff = utils_extras.get_total_diff(instance)

    assert abs(float(diff) - exact) < 1e-2

  @pytest.mark.parametrize([
    'value',
    'exact',
  ], [
    (-1, True),
    ( 0, False),
    ( 1, False),
  ], ids=[
    'is-negative',
    'is-zero',
    'is-positive',
  ])
  def test_check_is_negative_func(self, value, exact):
    ret = utils_extras.is_negative(value)

    assert ret == exact

  @pytest.mark.parametrize([
    'price',
    'dividend',
    'exact',
  ], [
    (1000,  20, 2.00),
    ( 143,   7, 4.90), # 7 / 143 * 100 -> 4.895... -> 4.90
    (   0, 123, 0.00),
    ( 0.0, 0.0, 0.00),
  ], ids=[
    'can-divide',
    'cannot-divide',
    'has-zero-division-error',
    'has-invalid-operation-error',
  ])
  def test_check_get_yield_func(self, price, dividend, exact):
    user = factories.UserFactory()
    stock = factories.StockFactory(price=Decimal(str(price)), dividend=Decimal(str(dividend)))
    instance = factories.PurchasedStockFactory(user=user, stock=stock)
    ret = utils_extras.get_yield(instance)

    assert abs(float(ret) - exact) < 1e-2

  @pytest.mark.parametrize([
    'per',
    'pbr',
    'exact',
  ], [
    (12.0,   0.0,    0.0),
    ( 0.0,  12.0,    0.0),
    ( 0.91,  0.81,   0.74), # 0.7371 -> 0.74
    (12.35, 23.47, 289.85), # 289.8545 -> 289.85
  ], ids=[
    'per-is-zero',
    'pbr-is-zero',
    'both-values-are-non-zero',
    'bigger-than-one',
  ])
  def test_check_get_multi_per_pbr_func(self, per, pbr, exact):
    user = factories.UserFactory()
    stock = factories.StockFactory(per=Decimal(str(per)), pbr=Decimal(str(pbr)))
    instance = factories.PurchasedStockFactory(user=user, stock=stock)
    ret = utils_extras.get_multi_per_pbr(instance)

    assert abs(float(ret) - exact) < 1e-2