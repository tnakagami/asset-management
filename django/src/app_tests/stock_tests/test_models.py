import pytest
import json
from django.db.utils import IntegrityError, DataError
from django.core.validators import ValidationError
from django.utils import timezone as djangoTimeZone
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from stock import models
from . import factories

@pytest.fixture
def get_judgement_funcs():
  def collector(classname, exclude=None):
    ignores = ['id'] if exclude is None else ['id'] + exclude
    return [field.name for field in classname._meta.fields if field.name not in ignores]
  def compare_keys(targets, exacts):
    return (len(targets) == len(exacts)) and all([name == exact_name for name, exact_name in zip(targets, exacts)])
  def compare_values(fields, targets, instance):
    _convertor = lambda val: float(val) if isinstance(val, Decimal) else val
    out = [targets[key] == _convertor(getattr(instance, key)) for key in fields]
    ret= all(out)
    print(ret, out)

    return ret

  return collector, compare_keys, compare_values

@pytest.fixture(params=[
  ('UTC',        datetime(2010,3,15,20,15,0, tzinfo=timezone.utc), '2010-03-15'),
  ('Asia/Tokyo', datetime(2010,3,15,20,15,0, tzinfo=timezone.utc), '2010-03-16'),
])
def pseudo_date(request):
  yield request.param

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_industry():
  industry = factories.IndustryFactory()

  assert isinstance(industry, models.Industry)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_snapshot():
  snapshot = factories.SnapshotFactory()

  assert isinstance(snapshot, models.Snapshot)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_stock():
  stock = factories.StockFactory()

  assert isinstance(stock, models.Stock)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_cash():
  cash = factories.CashFactory()

  assert isinstance(cash, models.Cash)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_purchased_stock():
  purchased_stock = factories.PurchasedStockFactory()

  assert isinstance(purchased_stock, models.PurchasedStock)

# ================
# Global functions
# ================
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.parametrize([
  'this_timezone',
  'target',
  'is_string',
  'strformat',
  'expected',
], [
  ('UTC', datetime(2000,1,2,10,0,0, tzinfo=timezone.utc), False, '', datetime(2000,1,2,10,0,0, tzinfo=ZoneInfo('UTC'))),
  ('UTC', datetime(2000,1,2,10,0,0, tzinfo=timezone.utc), True, '%Y-%m-%d %H:%M', '2000-01-02 10:00'),
  ('Asia/Tokyo', datetime(2000,1,2,10,0,0, tzinfo=timezone.utc), False, '', datetime(2000,1,2,19,0,0, tzinfo=ZoneInfo('Asia/Tokyo'))),
  ('Asia/Tokyo', datetime(2000,1,2,10,0,0, tzinfo=timezone.utc), True, '%Y-%m-%d %H:%M', '2000-01-02 19:00'),
], ids=[
  'to-utc-datetime',
  'to-utc-string',
  'to-asia-tokyo-datetime',
  'to-asia-tokyo-string',
])
def test_check_convert_timezone(settings, this_timezone, target, is_string, strformat, expected):
  settings.TIME_ZONE = this_timezone
  output = models.convert_timezone(target, is_string=is_string, strformat=strformat)

  assert output == expected

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.parametrize([
  'code',
], [
  ('1234', ),
  ('ABCD', ),
  ('xyzw', ),
  ('ABxy', ),
  ('A7890', ),
  ('a3456', ),
  ('', ),
], ids=[
  'only-numbers',
  'only-alphabets-of-capital-letter',
  'only-alphabets-of-small-letter',
  'only-alphabets-of-both-capital-and-small-letter',
  'both-numbers-and-capital-letter',
  'both-numbers-and-small-letter',
  'code-is-blank',
])
def test_check_valid_code_of_validate_code(code):
  try:
    models._validate_code(code)
  except Exception as ex:
    pytest.fail(f'Unexpected Error({code}): {ex}')

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.parametrize([
  'code',
], [
  ('a-123', ),
  ('1.23', ),
  ('2+ab0', ),
  ('3@aB', ),
  ('4#Ab', ),
  ('5$AB', ),
  ('6!23A', ),
  ('7&23b', ),
  ('-1234', ),
  ('1234-', ),
], ids=[
  'exists-hyphen',
  'exists-period',
  'exists-plus-mark',
  'exists-at-mark',
  'exists-sharp',
  'exists-dollar-mark',
  'exists-exclamation-mark',
  'exists-ampersand',
  'exists-top-symbol',
  'exists-last-symbol',
])
def test_check_invalid_code_of_validate_code(code):
  with pytest.raises(ValidationError) as ex:
    models._validate_code(code)
  assert 'either alphabets or numbers' in str(ex.value)

# ========
# Industry
# ========
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'name',
  'is_defensive',
  'original_type',
], [
  ('same-industry', True, True),
  ('same-industry', True, False),
  ('same-industry', False, True),
  ('same-industry', False, False),
], ids=[
  'both-are-defensive',
  'new-one-is-defensive',
  'new-one-is-not-defensive',
  'both-are-not-defensive',
])
def test_add_same_name_in_industry(name, is_defensive, original_type):
  _ = models.Industry.objects.create(name=name, is_defensive=original_type)

  with pytest.raises(IntegrityError) as ex:
    _ = models.Industry.objects.create(
      name=name,
      is_defensive=is_defensive,
    )
  assert 'unique constraint' in str(ex.value)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_get_dict_function_of_industry(get_judgement_funcs):
  collector, compare_keys, compare_values = get_judgement_funcs
  instance = factories.IndustryFactory()
  out_dict = instance.get_dict()
  fields = collector(models.Industry)

  assert compare_keys(list(out_dict.keys()), fields)
  assert compare_values(fields, out_dict, instance)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_industry_str_function():
  instance = factories.IndustryFactory()
  out = str(instance)

  assert out == instance.name

# =====
# Stock
# =====
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'code',
], [
  ('1234', ),
  ('abcd', ),
  ('ABCD', ),
  ('12ab', ),
  ('12AB', ),
], ids=[
  'only-numbers',
  'only-small-letters',
  'only-capital-letters',
  'both-numbers-and-small-letters',
  'both-numbers-and-capital-letters',
])
def test_add_same_code_in_stock(code):
  _ = factories.StockFactory(code=code)

  with pytest.raises(ValidationError) as ex:
    _ = factories.StockFactory(code=code)
  assert 'Stock code already exists' in str(ex.value)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'options',
], [
  ({}, ),
  ({'price': 0}, ),
  ({'price': 99999999.99}, ),
  ({'dividend': 0}, ),
  ({'dividend': 99999.99}, ),
  ({'per': 0}, ),
  ({'per': 99999.99}, ),
  ({'pbr': 0}, ),
  ({'pbr': 99999.99}, ),
  ({'eps': 0}, ),
  ({'eps': 99999.99}, ),
], ids=[
  'valid-values',
  'min-value-of-price',
  'max-value-of-price',
  'min-value-of-dividend',
  'max-value-of-dividend',
  'min-value-of-per',
  'max-value-of-per',
  'min-value-of-pbr',
  'max-value-of-pbr',
  'min-value-of-eps',
  'max-value-of-eps',
])
def test_check_valid_inputs_of_stock(options):
  kwargs = {
    'price':    Decimal('1.23'), 
    'dividend': Decimal('12.0'), 
    'per':      Decimal('1.07'), 
    'pbr':      Decimal('2.0'),
    'eps':      Decimal('1.12'),
  }
  kwargs.update(options)

  try:
    _ = models.Stock.objects.create(
      code='1234',
      name='sample',
      industry=factories.IndustryFactory(),
      **kwargs,
    )
  except ValidationError as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'options',
  'err_idx',
  'digit',
], [
  ({'price':    -0.01}, 0, 10), ({'price':    78.991}, 1, 2), ({'price':    100000000.00}, 2, 8),
  ({'dividend': -0.01}, 0,  7), ({'dividend': 78.991}, 1, 2), ({'dividend':   1000000.00}, 2, 5),
  ({'per':      -0.01}, 0,  7), ({'per':      78.991}, 1, 2), ({'per':        1000000.00}, 2, 5),
  ({'pbr':      -0.01}, 0,  7), ({'pbr':      78.991}, 1, 2), ({'pbr':        1000000.00}, 2, 5),
  ({'eps':      -0.01}, 0,  7), ({'eps':      78.991}, 1, 2), ({'eps':        1000000.00}, 2, 5),
], ids=[
  'negative-price',    'invalid-decimal-part-of-price',    'invalid-max-digits-of-price',
  'negative-dividend', 'invalid-decimal-part-of-dividend', 'invalid-max-digits-of-dividend',
  'negative-per',      'invalid-decimal-part-of-per',      'invalid-max-digits-of-per',
  'negative-pbr',      'invalid-decimal-part-of-pbr',      'invalid-max-digits-of-pbr',
  'negative-eps',      'invalid-decimal-part-of-eps',      'invalid-max-digits-of-eps',
])
def test_check_invalid_inputs_of_stock(options, err_idx, digit):
  err_types = [
    'digits in total',
    'decimal places',
    'digits before the decimal point',
  ]
  _type = err_types[err_idx]
  err_msg = f'Ensure that there are no more than {digit} {_type}'

  with pytest.raises(ValidationError) as ex:
    _ = models.Stock.objects.create(
      code='1234',
      name='sample',
      industry=factories.IndustryFactory(),
      **options,
    )
  assert err_msg in str(ex.value)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_get_dict_function_of_stock(get_judgement_funcs):
  collector, compare_keys, compare_values = get_judgement_funcs
  instance = factories.StockFactory()
  out_dict = instance.get_dict()
  fields = collector(models.Stock, exclude=['industry'])
  _industry = out_dict.pop('industry', None)

  assert _industry is not None
  assert compare_keys(list(out_dict.keys()), fields)
  assert compare_values(fields, out_dict, instance)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_stock_str_function():
  code = 1234
  name = 'X'
  instance = factories.StockFactory(code=code, name=name)
  out = str(instance)
  expected = f'{name}({code})'

  assert out == expected

# ====
# Cash
# ====
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'balance',
], [
  (0, ),
  (1, ),
  (2147483647, ),
], ids=[
  'is-zero',
  'is-one',
  'is-max',
])
def test_check_valid_balance_value(balance):
  user = factories.UserFactory()

  try:
    _ = models.Cash.objects.create(
      user=user,
      balance=balance,
      registered_date=djangoTimeZone.now(),
    )
  except IntegrityError as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'balance',
  'exception_type',
  'err_msg',
], [
  (-1, IntegrityError, 'violates check constraint'),
  (2147483647 + 1, DataError, 'integer out of range'),
], ids=[
  'is-negative',
  'is-overflow',
])
def test_check_invalid_balance_value(balance, exception_type, err_msg):
  user = factories.UserFactory()

  with pytest.raises(exception_type) as ex:
    _ = models.Cash.objects.create(
      user=user,
      balance=balance,
      registered_date=djangoTimeZone.now(),
    )
  assert err_msg in str(ex.value)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_get_dict_function_of_cash(get_judgement_funcs):
  collector, compare_keys, compare_values = get_judgement_funcs
  target_date = datetime(2022,3,4,10,9,1, tzinfo=timezone.utc)
  instance = factories.CashFactory(
    registered_date=target_date,
  )
  out_dict = instance.get_dict()
  fields = collector(models.Cash, exclude=['user', 'registered_date'])
  _registered_date = out_dict.pop('registered_date', None)

  assert _registered_date is not None
  assert compare_keys(list(out_dict.keys()), fields)
  assert compare_values(fields, out_dict, instance)
  assert _registered_date == target_date.strftime('%Y-%m-%d')

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_cash_str_function(settings, pseudo_date):
  this_timezone, target_date, exact_date = pseudo_date
  settings.TIME_ZONE = this_timezone
  instance = factories.CashFactory(
    user=factories.UserFactory(),
    balance=12345,
    registered_date=target_date,
  )
  out = str(instance)
  expected = f'{instance.balance}({exact_date})'

  assert out == expected

# ==============
# PurchasedStock
# ==============
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_get_dict_function_of_purchased_stock(get_judgement_funcs):
  collector, compare_keys, compare_values = get_judgement_funcs
  target_date = datetime(2022,3,4,10,9,1, tzinfo=timezone.utc)
  instance = factories.PurchasedStockFactory(
    purchase_date=target_date,
  )
  out_dict = instance.get_dict()
  fields = collector(models.PurchasedStock, exclude=['user', 'stock', 'purchase_date'])
  _stock = out_dict.pop('stock', None)
  _purchase_date = out_dict.pop('purchase_date', None)

  assert _stock is not None
  assert _purchase_date is not None
  assert compare_keys(list(out_dict.keys()), fields)
  assert compare_values(fields, out_dict, instance)
  assert _purchase_date == target_date.strftime('%Y-%m-%d')

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_purchased_stock_str_function(settings, pseudo_date):
  this_timezone, target_date, exact_date = pseudo_date
  settings.TIME_ZONE = this_timezone
  instance = factories.PurchasedStockFactory(
    user=factories.UserFactory(),
    stock=factories.StockFactory(),
    purchase_date=target_date,
    count=100,
  )
  out = str(instance)
  expected = f'{instance.stock.name}({exact_date},{instance.count})'

  assert out == expected

# ========
# Snapshot
# ========
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_that_json_field_is_empty_in_snapshot():
  instance = models.Snapshot.objects.create(
    user=factories.UserFactory(),
    title='Detail field is empty',
  )
  out_dict = json.loads(instance.detail)

  assert all(key in out_dict.keys() for key in ['cash', 'purchased_stocks'])
  assert len(out_dict['cash']) == 0
  assert len(out_dict['purchased_stocks']) == 0

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'balances',
  'months_days',
  'exact_idx',
], [
  ([123], [(2,10)], 0),
  ([123, 456], [(1,30), (2,9)], 1),
  ([123, 789, 456], [(2,1), (2,15), (1,30)], 1),
], ids=[
  'only-one-cash-is-recorded',
  'multi-cashes-are-recorded',
  'newest-record-is-mixed',
])
def test_check_that_cashes_exist_in_snapshot(balances, months_days, exact_idx):
  user = factories.UserFactory()

  for balance, month_day in zip(balances, months_days):
    target_date = datetime(2024,*month_day,1,2,3, tzinfo=timezone.utc)
    _ = factories.CashFactory(
      user=user,
      balance=balance,
      registered_date=target_date
    )

  instance = models.Snapshot.objects.create(
    user=user,
    title="User's cashes exist",
  )
  out_dict = json.loads(instance.detail)
  # Create exact data
  expected_balance = balances[exact_idx]
  expected_date = datetime(
    2024,*(months_days[exact_idx]),1,2,3,
    tzinfo=timezone.utc
  ).strftime('%Y-%m-%d')

  assert all(key in out_dict.keys() for key in ['cash', 'purchased_stocks'])
  assert len(out_dict['cash']) == 2
  assert len(out_dict['purchased_stocks']) == 0
  assert out_dict['cash']['balance'] == expected_balance
  assert out_dict['cash']['registered_date'] == expected_date

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'number_of_purchased_stocks',
], [
  (1, ),
  (3, ),
], ids=[
  'only-one-purchased_stock-exists',
  'multi-purchased_stocks-exist',
])
def test_check_that_purchased_stocks_exist_in_snapshot(number_of_purchased_stocks):
  user = factories.UserFactory()
  purchased_stocks = sorted(
    factories.PurchasedStockFactory.create_batch(number_of_purchased_stocks, user=user),
    key=lambda obj: obj.purchase_date,
    reverse=True,
  )
  instance = models.Snapshot.objects.create(
    user=user,
    title="User's purchsed stocks exist",
  )
  out_dict = json.loads(instance.detail)

  assert all(key in out_dict.keys() for key in ['cash', 'purchased_stocks'])
  assert len(out_dict['cash']) == 0
  assert len(out_dict['purchased_stocks']) == number_of_purchased_stocks
  assert all([
    all([
      extracted['stock']['name'] == exact_val.stock.name,
      extracted['purchase_date'] == exact_val.purchase_date.strftime('%Y-%m-%d'),
      extracted['count'] == exact_val.count,
    ])
    for extracted, exact_val in zip(out_dict['purchased_stocks'], purchased_stocks)
  ])

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_general_pattern_in_snapshot():
  user = factories.UserFactory()
  cashes = factories.CashFactory.create_batch(4, user=user)
  purchased_stocks = sorted(
    factories.PurchasedStockFactory.create_batch(4, user=user),
    key=lambda obj: obj.purchase_date,
    reverse=True,
  )
  instance = models.Snapshot.objects.create(
    user=user,
    title="It's general pattern",
  )
  out_dict = json.loads(instance.detail)
  # Create expected data
  exact_cash_idx, cash_date = 0, cashes[0].registered_date
  for idx, _cash in enumerate(cashes[1:], 1):
    if cash_date < _cash.registered_date:
      exact_cash_idx, cash_date = idx, _cash.registered_date

  assert all(key in out_dict.keys() for key in ['cash', 'purchased_stocks'])
  assert len(out_dict['cash']) == 2
  assert len(out_dict['purchased_stocks']) == 4
  assert out_dict['cash']['balance'] == cashes[exact_cash_idx].balance
  assert out_dict['cash']['registered_date'] == cashes[exact_cash_idx].registered_date.strftime('%Y-%m-%d')
  assert all([
    all([
      extracted['stock']['name'] == exact_val.stock.name,
      extracted['purchase_date'] == exact_val.purchase_date.strftime('%Y-%m-%d'),
      extracted['count'] == exact_val.count,
    ])
    for extracted, exact_val in zip(out_dict['purchased_stocks'], purchased_stocks)
  ])

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_snapshot_str_function(settings, pseudo_date):
  this_timezone, target_date, exact_date = pseudo_date
  settings.TIME_ZONE = this_timezone
  instance = factories.SnapshotFactory(
    user=factories.UserFactory(),
    title='sample-title',
    detail='{"key1":3,"key2":"a","key3":4}',
    created_at=target_date,
  )
  out = str(instance)
  expected = f'{instance.title}({exact_date})'

  assert out == expected