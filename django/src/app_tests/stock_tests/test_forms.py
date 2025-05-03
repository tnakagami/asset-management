import pytest
from datetime import datetime, timezone
from stock import forms
from . import factories

get_date = lambda day: datetime(2022,7,day,10,13,15, tzinfo=timezone.utc)

@pytest.fixture
def get_user(django_db_blocker):
  with django_db_blocker.unblock():
    user = factories.UserFactory()

  return user

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'params',
  'is_valid',
], [
  ({'balance': 10,  'registered_date': get_date(3)}, True),
  ({'balance':  0,  'registered_date': get_date(3)}, True),
  ({'balance': -1,  'registered_date': get_date(3)}, False),
  ({                'registered_date': get_date(3)}, False),
  ({'balance': 'a', 'registered_date': get_date(3)}, False),
  ({'balance': 10,  'registered_date':    '123456'}, False),
  ({'balance': 10,  'registered_date':       'abc'}, False),
  ({'balance': 10,                                }, False),
  ({                                              }, False),
], ids=[
  'valid-form-data',
  'balance-is-zero',
  'balance-is-negative',
  'balance-is-empty',
  'balance-is-string',
  'date-is-number',
  'date-is-string',
  'date-is-empty',
  'param-is-empty',
])
def test_cash_form(get_user, params, is_valid):
  user = get_user
  form = forms.CashForm(user=user, data=params)

  assert form.is_valid() == is_valid

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'exist_stock',
  'kwargs',
  'is_valid',
], [
  (True,  {'price':  10, 'purchase_date': get_date(3), 'count':   5}, True),
  (True,  {'price':   0, 'purchase_date': get_date(3), 'count':   5}, True),
  (True,  {'price':  10, 'purchase_date': get_date(3), 'count':   0}, True),
  (False, {'price':  10, 'purchase_date': get_date(3), 'count':   5}, False),
  (True,  {'price':  -1, 'purchase_date': get_date(3), 'count':   5}, False),
  (True,  {'price': 'a', 'purchase_date': get_date(3), 'count':   5}, False),
  (True,  {'price':  10, 'purchase_date':    '123456', 'count':   5}, False),
  (True,  {'price':  10, 'purchase_date':       'abc', 'count':   5}, False),
  (True,  {'price':  10, 'purchase_date': get_date(3), 'count':  -1}, False),
  (True,  {'price':  10, 'purchase_date': get_date(3), 'count': 'a'}, False),
  (True,  {              'purchase_date': get_date(3), 'count':   5}, False),
  (True,  {'price':  10,                               'count':   5}, False),
  (True,  {'price':  10, 'purchase_date': get_date(3),             }, False),
  (False, {                                                        }, False),
], ids=[
  'valid-form-data',
  'price-is-zero',
  'count-is-zero',
  'stock-is-empty',
  'price-is-negative',
  'price-is-string',
  'date-is-number',
  'date-is-string',
  'count-is-negative',
  'count-is-string',
  'price-is-empty',
  'date-is-empty',
  'count-is-empty',
  'param-is-empty',
])
def test_purchased_stock_form(get_user, exist_stock, kwargs, is_valid):
  user = get_user
  instance = factories.StockFactory()
  params = {}
  # Check stock status
  if exist_stock:
    params['stock'] = instance.pk
  # Set rest params
  for key, val in kwargs.items():
    params[key] = val
  form = forms.PurchasedStockForm(user=user, data=params)

  assert form.is_valid() == is_valid

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
def test_check_purchased_stock_choices_in_its_form():
  user = factories.UserFactory()
  stock_data = [
    {'name': 'sample1', 'code': '123c'},
    {'name': 'sample2', 'code': 'a456'},
  ]
  exact_vals = {}

  for idx, kwargs in enumerate(stock_data):
    instance = factories.StockFactory(**kwargs)
    exact_vals[instance.pk] = kwargs

  form = forms.PurchasedStockForm(user=user)
  choices = form.stock_choices
  compare = lambda estimate, exact: all([estimate['name'] == exact['name'], estimate['code'] == exact['code']])
  _1st = choices[0]
  _2nd = choices[1]

  assert compare(_1st, exact_vals[_1st['pk']])
  assert compare(_2nd, exact_vals[_2nd['pk']])

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'params',
  'is_valid',
], [
  ({'title': 'sample', 'start_date': get_date(2), 'end_date': get_date(28)}, True),
  ({'title': 'sample',                            'end_date': get_date(28)}, True),
  ({'title': 'sample', 'start_date': get_date(2)                          }, False),
  ({                   'start_date': get_date(2), 'end_date': get_date(28)}, False),
  ({'title': 'sample', 'start_date':       'abc', 'end_date': get_date(28)}, False),
  ({'title': 'sample', 'start_date':       '123', 'end_date': get_date(28)}, False),
  ({'title': 'sample', 'start_date': get_date(2), 'end_date':        'abc'}, False),
  ({'title': 'sample', 'start_date': get_date(2), 'end_date':        '123'}, False),
  ({                                                                      }, False),
], ids=[
  'valid-form-data',
  'start-date-is-empty',
  'end-date-is-empty',
  'title-is-empty',
  'start-date-is-string',
  'start-date-is-invalid',
  'end-date-is-string',
  'end-date-is-invalid',
  'param-is-empty',
])
def test_snapshot_form(get_user, params, is_valid):
  user = get_user
  form = forms.SnapshotForm(user=user, data=params)

  assert form.is_valid() == is_valid