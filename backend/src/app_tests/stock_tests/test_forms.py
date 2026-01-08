import pytest
import ast
import json
from django.core.exceptions import ValidationError
from django_celery_beat.models import PeriodicTask
from datetime import datetime, timezone
from stock.models import PurchasedStock, Stock, Snapshot
from stock import forms
from . import factories

get_date = lambda day: datetime(2022,7,day,10,13,15, tzinfo=timezone.utc)

class _DummyASTCondition:
  def __init__(self, *args, **kwargs):
    pass

  def visit(self, node):
    pass

  def validate(self):
    pass

@pytest.fixture
def get_user(django_db_blocker):
  with django_db_blocker.unblock():
    user = factories.UserFactory()

  return user

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.parametrize([
  'value',
  'expected',
], [
  ('True', True),
  ('true', True),
  ('TRUE', True),
  ('1', True),
  ('False', False),
  ('false', False),
  ('FALSE', False),
  ('0', False),
  (False, False),
], ids=[
  'python-style-true',
  'javascript-style-true',
  'Excel-style-true',
  'number-style-true',
  'python-style-false',
  'javascript-style-false',
  'Excel-style-false',
  'number-style-false',
  'boolean-style-false',
])
def test_bool_converter(value, expected):
  estimated = forms.bool_converter(value)

  assert estimated == expected

@pytest.mark.stock
@pytest.mark.form
def test_check_ignore_field_class():
  try:
    instance = forms._IgnoredField()
    instance.clean(3, None)
  except Exception as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.parametrize([
  'condition',
], [
  ('2<er<4', ),
  ('price < 10\n and bps > 10', ),
], ids=[
  'simple-pattern',
  'with-return-code',
])
def test_valid_patterns_of_validate_filtering_condition(mocker, condition):
  mocker.patch('stock.forms._ValidateCondition', new=_DummyASTCondition)

  try:
    forms.validate_filtering_condition(condition)
  except Exception as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.parametrize([
  'method_name',
  'exception',
  'err_msg',
], [
  ('visit', SyntaxError('invalid-input'), 'Invalid syntax: invalid-input'),
  ('visit', IndexError('invalid-index'), 'Invalid syntax: invalid-index'),
  ('validate', KeyError('invalid-key'), "Invalid variable: \'invalid-key\'"),
],ids=[
  'raise-syntax-error',
  'raise-index-error',
  'raise-key-error',
])
def test_invalid_patterns_of_validate_filtering_condition(mocker, method_name, exception, err_msg):
  mocker.patch('stock.forms._ValidateCondition', new=_DummyASTCondition)
  mocker.patch(f'stock.forms._ValidateCondition.{method_name}', side_effect=exception)

  with pytest.raises(ValidationError) as ex:
    forms.validate_filtering_condition('price < 100')

  assert err_msg in str(ex.value)

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.parametrize([
  'condition',
], [
  ('name == "cone"', ),
  ('name != "cone"', ),
  ('price <  10', ),
  ('price <= 11', ),
  ('price >  12', ),
  ('price >= 13', ),
  ('100 < price <= 200', ),
  ('bps <= 0.2 < eps < 0.5 < er < 0.75', ),
  ('name in "hoge"', ),
  ('name not in "hoge"', ),
  ('name in "foo" and price < 100', ),
  ('name in "foo" or price < 100', ),
  ('price < 100 or eps < 0.2 and er > 0.5', ),
  ('(price < 100 or eps < 0.2) and er > 0.5', ),
], ids=[
  'check-compare-eq',
  'check-compare-not-eq',
  'check-compare-lt',
  'check-compare-lte',
  'check-compare-gt',
  'check-compare-gte',
  'check-compare-between-ops',
  'check-compare-multi-ops-and-vars',
  'check-compare-in',
  'check-compare-not-in',
  'check-boolop-and',
  'check-boolop-or',
  'check-boolop-both-ops',
  'check-boolop-both-with-bracket',
])
def test_valid_visit_method_for_validateCondition(condition):
  visitor = forms._ValidateCondition()
  tree = ast.parse(condition, mode='eval')

  try:
    visitor.visit(tree)
  except Exception as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.parametrize([
  'condition',
], [
  ('code == "cone"', ), ('code != "cone"', ), ('code in "cone"', ), ('code not in "cone"', ),
  ('name == "cone"', ), ('name != "cone"', ), ('name in "cone"', ), ('name not in "cone"', ),
  ('industry_name == "cone"', ), ('industry_name != "cone"', ), ('industry_name in "cone"', ), ('industry_name not in "cone"', ),
  ('price == 10.0', ), ('price != 10.0', ), ('price < 10.0', ), ('price <= 10.0', ), ('price > 10.0', ), ('price >= 10.0', ),
  ('dividend == 10.0', ), ('dividend != 10.0', ), ('dividend < 10.0', ), ('dividend <= 10.0', ), ('dividend > 10.0', ), ('dividend >= 10.0', ),
  ('per == 10.0', ), ('per != 10.0', ), ('per < 10.0', ), ('per <= 10.0', ), ('per > 10.0', ), ('per >= 10.0', ),
  ('pbr == 10.0', ), ('pbr != 10.0', ), ('pbr < 10.0', ), ('pbr <= 10.0', ), ('pbr > 10.0', ), ('pbr >= 10.0', ),
  ('eps == 10.0', ), ('eps != 10.0', ), ('eps < 10.0', ), ('eps <= 10.0', ), ('eps > 10.0', ), ('eps >= 10.0', ),
  ('bps == 10.0', ), ('bps != 10.0', ), ('bps < 10.0', ), ('bps <= 10.0', ), ('bps > 10.0', ), ('bps >= 10.0', ),
  ('roe == 10.0', ), ('roe != 10.0', ), ('roe < 10.0', ), ('roe <= 10.0', ), ('roe > 10.0', ), ('roe >= 10.0', ),
  ('er == 10.0', ), ('er != 10.0', ), ('er < 10.0', ), ('er <= 10.0', ), ('er > 10.0', ), ('er >= 10.0', ),
], ids=[
  'check-code-with-eq', 'check-code-with-not-eq', 'check-code-with-in', 'check-code-with-not-in',
  'check-name-with-eq', 'check-name-with-not-eq', 'check-name-with-in', 'check-name-with-not-in',
  'check-industry-with-eq', 'check-industry-with-not-eq', 'check-industry-with-in', 'check-industry-with-not-in',
  'check-price-with-eq', 'check-price-with-not-eq', 'check-price-with-lt', 'check-price-with-lte', 'check-price-with-gt', 'check-price-with-gte',
  'check-dividend-with-eq', 'check-dividend-with-not-eq', 'check-dividend-with-lt', 'check-dividend-with-lte', 'check-dividend-with-gt', 'check-dividend-with-gte',
  'check-per-with-eq', 'check-per-with-not-eq', 'check-per-with-lt', 'check-per-with-lte', 'check-per-with-gt', 'check-per-with-gte',
  'check-pbr-with-eq', 'check-pbr-with-not-eq', 'check-pbr-with-lt', 'check-pbr-with-lte', 'check-pbr-with-gt', 'check-pbr-with-gte',
  'check-eps-with-eq', 'check-eps-with-not-eq', 'check-eps-with-lt', 'check-eps-with-lte', 'check-eps-with-gt', 'check-eps-with-gte',
  'check-bps-with-eq', 'check-bps-with-not-eq', 'check-bps-with-lt', 'check-bps-with-lte', 'check-bps-with-gt', 'check-bps-with-gte',
  'check-roe-with-eq', 'check-roe-with-not-eq', 'check-roe-with-lt', 'check-roe-with-lte', 'check-roe-with-gt', 'check-roe-with-gte',
  'check-er-with-eq', 'check-er-with-not-eq', 'check-er-with-lt', 'check-er-with-lte', 'check-er-with-gt', 'check-er-with-gte',
])
def test_valid_validate_method_for_validateCondition(condition):
  visitor = forms._ValidateCondition()
  tree = ast.parse(condition, mode='eval')
  visitor.visit(tree)

  try:
    visitor.validate()
  except Exception as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.parametrize([
  'condition',
  'err_msg',
], [
  ('a + b',  'cannot use BinOp in this application'),
  ('a - b',  'cannot use BinOp in this application'),
  ('a * b',  'cannot use BinOp in this application'),
  ('a ** b', 'cannot use BinOp in this application'),
  ('a / b',  'cannot use BinOp in this application'),
  ('a % 3',  'cannot use BinOp in this application'),
  ('a // b', 'cannot use BinOp in this application'),
  ('a >> b', 'cannot use BinOp in this application'),
  ('a << b', 'cannot use BinOp in this application'),
  ('price < f(3)', 'cannot use Call in this application'),
  ('price.dummy < 10', 'cannot use Attribute in this application'),
], ids=[
  'use-add-op',
  'use-sub-op',
  'use-mult-op',
  'use-pow-op',
  'use-div-op',
  'use-mod-op',
  'use-floor-div-op',
  'use-right-shift-op',
  'use-left-shift-op',
  'use-call',
  'use-attribute',
])
def test_invalid_operator_for_validateCondition(condition, err_msg):
  visitor = forms._ValidateCondition()
  tree = ast.parse(condition, mode='eval')

  with pytest.raises(SyntaxError) as ex:
    visitor.visit(tree)

  assert err_msg in str(ex.value)

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.parametrize([
  'condition',
  'exception_type',
  'err_msg',
], [
  ('industry == "hoge"', KeyError, 'industry does not exist'),
  ('price < 10.001', ValidationError, 'Invalid data (price, 10.001): '),
  ('code < "1200"', ValidationError, 'Invalid operator between code and 1200'),
  ('price in 1200', ValidationError, 'Invalid operator between price and 1200'),
], ids=[
  'invalid-keyname',
  'invalid-field-value',
  'invalid-operator-for-str',
  'invalid-operator-for-number',
])
def test_invalid_pattern_of_validation_method_for_validateCondition(condition, exception_type, err_msg):
  visitor = forms._ValidateCondition()
  tree = ast.parse(condition, mode='eval')
  visitor.visit(tree)

  with pytest.raises(exception_type) as ex:
    visitor.validate()

  assert err_msg in str(ex.value)

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
  (True,  {'price':  10, 'purchase_date': get_date(3), 'count':   5, 'has_been_sold': False}, True),
  (True,  {'price':   0, 'purchase_date': get_date(3), 'count':   5, 'has_been_sold': False}, True),
  (True,  {'price':  10, 'purchase_date': get_date(3), 'count':   0, 'has_been_sold': False}, True),
  (True,  {'price':   7, 'purchase_date': get_date(3), 'count':   2, 'has_been_sold': True},  True),
  (False, {'price':  10, 'purchase_date': get_date(3), 'count':   5, 'has_been_sold': False}, False),
  (True,  {'price':  -1, 'purchase_date': get_date(3), 'count':   5, 'has_been_sold': False}, False),
  (True,  {'price': 'a', 'purchase_date': get_date(3), 'count':   5, 'has_been_sold': False}, False),
  (True,  {'price':  10, 'purchase_date':    '123456', 'count':   5, 'has_been_sold': False}, False),
  (True,  {'price':  10, 'purchase_date':       'abc', 'count':   5, 'has_been_sold': False}, False),
  (True,  {'price':  10, 'purchase_date': get_date(3), 'count':  -1, 'has_been_sold': False}, False),
  (True,  {'price':  10, 'purchase_date': get_date(3), 'count': 'a', 'has_been_sold': False}, False),
  (True,  {              'purchase_date': get_date(3), 'count':   5, 'has_been_sold': False}, False),
  (True,  {'price':  10,                               'count':   5, 'has_been_sold': False}, False),
  (True,  {'price':  10, 'purchase_date': get_date(3),               'has_been_sold': False}, False),
  (False, {                                                                                }, False),
], ids=[
  'valid-form-data',
  'price-is-zero',
  'count-is-zero',
  'stock-has-been-sold',
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
def test_check_stock_pk_is_invalid(get_user):
  user = get_user
  instance = factories.StockFactory()
  params = {
    'stock': instance.pk+1,
    'price': 10,
    'purchase_date': get_date(3),
    'count': 5,
  }
  form = forms.PurchasedStockForm(user=user, data=params)
  is_valid = form.is_valid()

  assert not is_valid
  assert form.fields['stock'].widget._has_error

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
def test_stock_field_doesnot_have_error(mocker, get_user):
  user = get_user
  stock = factories.StockFactory()
  instance = factories.PurchasedStockFactory(user=user, stock=stock)
  params = {
    'stock': stock.pk,
    'price': 10,
    'purchase_date': get_date(3),
    'count': 5,
    'has_been_sold': False,
  }
  form = forms.PurchasedStockForm(user=user, data=params)
  form.fields['stock'].error_messages = {}
  is_valid = form.is_valid()

  assert is_valid
  assert len(form.fields['stock'].error_messages) == 0

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
def test_check_valid_update_queryset_in_pstock_form(get_user):
  user = get_user
  instances = factories.PurchasedStockFactory.create_batch(3, user=user)
  params = {
    'stock': instances[1].stock.pk,
    'price': 10,
    'purchase_date': get_date(3),
    'count': 5,
  }
  form = forms.PurchasedStockForm(user=user, data=params)
  target_pk = instances[0].pk
  target_stock_pk = instances[0].stock.pk
  form.update_queryset(pk=target_pk)
  qs = form.fields['stock'].queryset
  count = qs.count()
  the1st_stock = qs.first()

  assert count == 1
  assert the1st_stock.pk == target_stock_pk

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
def test_check_invalid_update_queryset_in_pstock_form(get_user):
  user = get_user
  instance = factories.PurchasedStockFactory(user=user)
  params = {
    'stock': instance.stock.pk,
    'price': 10,
    'purchase_date': get_date(3),
    'count': 5,
  }
  form = forms.PurchasedStockForm(user=user, data=params)
  target_pk = instance.pk + 1

  with pytest.raises(PurchasedStock.DoesNotExist) as ex:
    form.update_queryset(pk=target_pk)

  assert 'matching query does not exist' in str(ex.value)

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'arg_idx',
  'checker',
], [
  (0, lambda ret: isinstance(ret, Stock)),
  (1, lambda ret: isinstance(ret, Stock)),
  (2, lambda ret: ret is None),
  (3, lambda ret: ret is None),
  (4, lambda ret: ret is None),
  (5, lambda ret: ret is None),
  (6, lambda ret: ret is None),
], ids=[
  'value-is-primary-key',
  'value-is-instance',
  'value-is-None',
  'value-is-empty-string',
  'value-is-empty-list',
  'value-is-empty-dict',
  'value-is-empty-tuple',
])
def test_check_valid_custom_modeldatalist_field(arg_idx, checker):
  stocks = factories.StockFactory.create_batch(2)
  _vals = [
    stocks[0].pk,
    stocks[1],
    None,
    '',
    [],
    {},
    (),
  ]
  value = _vals[arg_idx]
  field = forms.CustomModelDatalistField(queryset=Stock.objects.all())
  ret = field.to_python(value)

  assert checker(ret)

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'arg_idx',
], [
  (0, ),
  (1, ),
  (2, ),
], ids=[
  'raise-type-error',
  'raise-value-error',
  'raise-invalid-pk',
])
def test_check_invalid_custom_modeldatalist_field(arg_idx):
  err_code = 'invalid_choice'
  stocks = factories.StockFactory.create_batch(3)
  _vals = [
    [2],
    -1,
    stocks[-1].pk + 1,
  ]
  field = forms.CustomModelDatalistField(queryset=Stock.objects.all())

  with pytest.raises(ValidationError) as ex:
    _ = field.to_python(_vals[arg_idx])

  assert 'Select a valid choice' in str(ex.value)

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'params',
  'is_valid',
], [
  ({'title': 'sample', 'priority': 99, 'start_date': get_date(2), 'end_date': get_date(28)}, True),
  ({'title': 'sample', 'priority': 99,                            'end_date': get_date(28)}, True),
  ({'title': 'sample', 'priority': 99, 'start_date': get_date(2)                          }, False),
  ({                   'priority': 99, 'start_date': get_date(2), 'end_date': get_date(28)}, False),
  ({'title': 'sample',                 'start_date': get_date(2), 'end_date': get_date(28)}, False),
  ({'title': 'sample', 'priority': 99, 'start_date':       'abc', 'end_date': get_date(28)}, False),
  ({'title': 'sample', 'priority': 99, 'start_date':       '123', 'end_date': get_date(28)}, False),
  ({'title': 'sample', 'priority': 99, 'start_date': get_date(2), 'end_date':        'abc'}, False),
  ({'title': 'sample', 'priority': 99, 'start_date': get_date(2), 'end_date':        '123'}, False),
  ({                                                                                      }, False),
], ids=[
  'valid-form-data',
  'start-date-is-empty',
  'end-date-is-empty',
  'title-is-empty',
  'priority-is-empty',
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

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'forced_update',
  'commit',
  'output_dlen', # data length of detail for returned value
  'record_dlen', # data length of detail for database record
], [
  (True, True, 2, 2),
  (True, False, 2, 0),
  (False, True, 0, 0),
  (False, False, 0, 0),
], ids=[
  'forced-update-and-commit',
  'only-forced-update',
  'only-commit',
  'do-nothing',
])
def test_save_method_of_snapshot(get_user, forced_update, commit, output_dlen, record_dlen):
  user = get_user
  _ = factories.CashFactory.create_batch(2, user=user)
  _ = factories.PurchasedStockFactory.create_batch(3, user=user)
  instance = factories.SnapshotFactory(user=user, title='snapshot to call save method')
  # Forced detail field update
  instance.detail = json.dumps({})
  instance.save()
  # Create the parameters for form fields
  params = {
    'title': 'sample',
    'priority': 99,
    'start_date': get_date(2),
    'end_date': get_date(28),
    'forced_update': forced_update,
  }
  form = forms.SnapshotForm(user=user, data=params)
  form.instance = instance
  is_valid = form.is_valid()
  output = form.save(commit=commit)
  estimated = Snapshot.objects.get(pk=instance.pk)
  detail_output = json.loads(output.detail)
  detail_estimated = json.loads(estimated.detail)

  assert is_valid
  assert len(detail_output) == output_dlen
  assert len(detail_estimated) == record_dlen

@pytest.fixture
def pseudo_periodic_task_params(django_db_blocker, get_user):
  with django_db_blocker.unblock():
    user = get_user
    _ = factories.CashFactory.create_batch(2, user=user)
    _ = factories.PurchasedStockFactory.create_batch(3, user=user)
    _ = factories.SnapshotFactory(user=user)
    _ = factories.CashFactory.create_batch(3, user=user)
    _ = factories.PurchasedStockFactory.create_batch(2, user=user)
    snapshot = factories.SnapshotFactory(user=user)
  # It is the pattern of  `schedule_type` == `every-day`
  params = {
    'name': 'hoge',
    'enabled': True,
    'snapshot': snapshot.pk,
    'schedule_type': 'every-day',
    'config': {'minute': 23, 'hour': 13},
  }

  return user, params

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
def test_check_init_func_of_ptask_for_ss_form(get_user):
  user = get_user
  form = forms.PeriodicTaskForSnapshotForm(user=user)

  assert form.default_schedule == 'every-day'
  assert form.schedule_restriction['every-day'] == ['minute', 'hour']
  assert form.schedule_restriction['every-week'] == ['minute', 'hour', 'day_of_week']
  assert form.schedule_restriction['every-month'] == ['minute', 'hour', 'day_of_month']

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'param_cron',
  'callback',
  'expected_schedule_type',
], [
  ({'day_of_week': '*', 'day_of_month': '3'}, (lambda config: config['day_of_month'] == '3'), 'every-month'),
  ({'day_of_week': '1', 'day_of_month': '*'}, (lambda config: config['day_of_week'] == '1'), 'every-week'),
  ({'day_of_week': '*', 'day_of_month': '*'}, (lambda config: True), 'every-day'),
], ids=[
  'every-month',
  'every-week',
  'every-day',
])
def test_check_update_initial(get_user, param_cron, callback, expected_schedule_type):
  minute, hour = 9, 13
  user = get_user
  _ = factories.CashFactory.create_batch(2, user=user)
  _ = factories.PurchasedStockFactory.create_batch(3, user=user)
  snapshot = factories.SnapshotFactory(user=user)
  crontab = factories.CrontabScheduleFactory(minute=minute, hour=hour, **param_cron)
  task = factories.PeriodicTaskFactory(
    crontab=crontab,
    kwargs=json.dumps({'user_pk': user.pk, 'snapshot_pk': snapshot.pk}),
  )
  form = forms.PeriodicTaskForSnapshotForm(user=user)
  form.update_initial(task)
  config = json.loads(form.fields['config'].initial)
  schedule_type = form.fields['schedule_type'].initial
  instance = form.fields['snapshot'].initial

  assert instance.pk == snapshot.pk
  assert schedule_type == expected_schedule_type
  assert config['minute'] == minute
  assert config['hour'] == hour
  assert callback(config)

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
def test_unexpected_kwargs_in_update_initial(get_user):
  user = get_user
  task = factories.PeriodicTaskFactory(kwargs=json.dumps({'user_pk': user.pk, 'snapshot_pk': 0}))
  form = forms.PeriodicTaskForSnapshotForm(user=user)
  form.update_initial(task)
  instance = form.fields['snapshot'].initial

  assert instance is None

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
def test_basic_pattern_of_ptask_for_ss_form(pseudo_periodic_task_params):
  user, params = pseudo_periodic_task_params
  form = forms.PeriodicTaskForSnapshotForm(user=user, data=params)

  assert form.is_valid()

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'commit',
  'expected_count',
], [
  (True, 1),
  (False, 0),
], ids=[
  'commit',
  'not-commit',
])
def test_check_save_method_of_ptask_for_ss_form(pseudo_periodic_task_params, commit, expected_count):
  user, params = pseudo_periodic_task_params
  ss_pk = params['snapshot']
  form = forms.PeriodicTaskForSnapshotForm(user=user, data=params)
  is_valid = form.is_valid()
  instance = form.save(commit=commit)
  kwargs = json.dumps({'user_pk': user.pk, 'snapshot_pk': ss_pk})
  count = PeriodicTask.objects.filter(kwargs__contains=kwargs).count()
  snapshot = Snapshot.objects.get(pk=ss_pk)

  assert is_valid
  assert count == expected_count
  assert instance.task == 'stock.tasks.update_specific_snapshot'
  assert instance.description == snapshot.title

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'kwargs_to_update',
], [
  ({'schedule_type': 'every-day', 'config': {'minute': 23, 'hour': 13, 'hoge': 3, 'foo': 'ok'}},),
  ({'schedule_type': 'every-week', 'config': {'minute': 23, 'hour': 13, 'day_of_week': 6}},),
  ({'schedule_type': 'every-week', 'config': {'minute': 23, 'hour': 13, 'day_of_week': 'fri'}},),
  ({'schedule_type': 'every-week', 'config': {'minute': 23, 'hour': 13, 'day_of_week': 'mon-fri'}},),
  ({'schedule_type': 'every-month', 'config': {'minute': 23, 'hour': 13, 'day_of_month': 9}},),
  ({'enabled': False},),
], ids=[
  'every-day-with-garbage',
  'every-week-num',
  'every-week-str',
  'every-week-range',
  'every-month',
  'is-disable',
])
def test_customized_valid_pattern_of_ptask_for_ss_form(pseudo_periodic_task_params, kwargs_to_update):
  user, params = pseudo_periodic_task_params
  params.update(kwargs_to_update)
  form = forms.PeriodicTaskForSnapshotForm(user=user, data=params)

  assert form.is_valid()

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'kwargs_to_update',
  'delete_list',
  'err_msg',
], [
  # For name
  ({'name': ''}, [], 'This field is required.'),
  ({'name': '1'*201}, [], 'Ensure this value has at most 200 characters (it has 201).'),
  ({}, ['name'], 'This field is required.'),
  # For task
  ({'name': '1'*201}, [], 'Ensure this value has at most 200 characters (it has 201).'),
  # For enabled
  ({}, ['enabled'], 'This field is required.'),
  # For snapshot
  ({'snapshot': 0}, [], 'Select a valid choice. That choice is not one of the available choices.'),
  ({}, ['snapshot'], 'This field is required.'),
  # For schedule type
  ({'schedule_type': 'XXX'}, [], 'Select a valid choice. XXX is not one of the available choices.'),
  ({}, ['schedule_type'], 'This field is required.'),
  # ----------
  # For config
  # ----------
  # For every-day
  ({'schedule_type': 'every-day',   'config': {                                           }}, [], 'Required keys: minute,hour'),
  ({'schedule_type': 'every-day',   'config': {'minute': 23,                              }}, [], 'Required keys: hour'),
  ({'schedule_type': 'every-day',   'config': {              'hour': 13,                  }}, [], 'Required keys: minute'),
  # For every-week
  ({'schedule_type': 'every-week',  'config': {                                           }}, [], 'Required keys: minute,hour,day_of_week'),
  ({'schedule_type': 'every-week',  'config': {'minute': 23,                              }}, [], 'Required keys: hour,day_of_week'),
  ({'schedule_type': 'every-week',  'config': {'minute': 23, 'hour': 13,                  }}, [], 'Required keys: day_of_week'),
  ({'schedule_type': 'every-week',  'config': {              'hour': 13                   }}, [], 'Required keys: minute,day_of_week'),
  ({'schedule_type': 'every-week',  'config': {              'hour': 13, 'day_of_week':  6}}, [], 'Required keys: minute'),
  ({'schedule_type': 'every-week',  'config': {'minute': 23,             'day_of_week':  6}}, [], 'Required keys: hour'),
  ({'schedule_type': 'every-week',  'config': {                          'day_of_week':  6}}, [], 'Required keys: minute,hour'),
  # For every-month
  ({'schedule_type': 'every-month', 'config': {                                           }}, [], 'Required keys: minute,hour,day_of_month'),
  ({'schedule_type': 'every-month', 'config': {'minute': 23,                              }}, [], 'Required keys: hour,day_of_month'),
  ({'schedule_type': 'every-month', 'config': {'minute': 23, 'hour': 13,                  }}, [], 'Required keys: day_of_month'),
  ({'schedule_type': 'every-month', 'config': {              'hour': 13                   }}, [], 'Required keys: minute,day_of_month'),
  ({'schedule_type': 'every-month', 'config': {              'hour': 13, 'day_of_month': 9}}, [], 'Required keys: minute'),
  ({'schedule_type': 'every-month', 'config': {'minute': 23,             'day_of_month': 9}}, [], 'Required keys: hour'),
  ({'schedule_type': 'every-month', 'config': {                          'day_of_month': 9}}, [], 'Required keys: minute,hour'),
  ({'schedule_type': 'every-day'}, ['config'], 'This field is required.'),
], ids=[
  # For name
  'empty-name',
  'name-is-too-long',
  'name-is-not-set',
  # For task
  'task-is-too-long',
  # For enabled
  'empty-enabled',
  # For snapshot
  'invalid-snapshot-pk',
  'snapshot-is-not-set',
  # For schedule type
  'invalid-schedule-type',
  'schedule-type-is-not-set',
  # ----------
  # For config
  # ----------
  # For every-day
  'empty-config-for-every-day',
  'without-hour-for-every-day',
  'without-minute-for-every-day',
  # For every week
  'empty-config-for-every-week',
  'without-hour-week-for-every-week',
  'without-week-for-every-week',
  'without-minute-week-for-every-week',
  'without-minute-for-every-week',
  'without-hour-for-every-week',
  'without-minute-hour-for-every-week',
  # For every month
  'empty-config-for-every-month',
  'without-hour-month-for-every-month',
  'without-month-for-every-month',
  'without-minute-month-for-every-month',
  'without-minute-for-every-month',
  'without-hour-for-every-month',
  'without-minute-hour-for-every-month',
  'config-is-not-set',
])
def test_invalid_pattern_of_ptask_for_ss_form(pseudo_periodic_task_params, kwargs_to_update, delete_list, err_msg):
  user, params = pseudo_periodic_task_params
  params.update(kwargs_to_update)

  for key in delete_list:
    del params[key]
  form = forms.PeriodicTaskForSnapshotForm(user=user, data=params)
  is_valid = form.is_valid()

  assert not is_valid
  assert err_msg in str(form.errors)

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'schedule_type',
  'kwargs_to_update',
], [
  ('every-day', {'minute': -1, 'hour': 13}),
  ('every-day', {'minute': 23, 'hour': -1}),
  ('every-week', {'minute': 23, 'hour': 13, 'day_of_week': -1}),
  ('every-month', {'minute': 23, 'hour': 13, 'day_of_month': -1}),
], ids=[
  'invalid-minute-of-every-day',
  'invalid-hour-of-every-day',
  'invalid-week-of-every-week',
  'invalid-month-of-every-month',
])
def test_invalid_crontab_of_ptask_for_ss_form(pseudo_periodic_task_params, schedule_type, kwargs_to_update):
  user, params = pseudo_periodic_task_params
  params.update({
    'schedule_type': schedule_type,
    'config': kwargs_to_update,
  })
  form = forms.PeriodicTaskForSnapshotForm(user=user, data=params)
  is_valid = form.is_valid()
  err_msg = 'Invalid crontab config:'

  assert not is_valid
  assert err_msg in str(form.errors)

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.parametrize([
  'params',
  'exacts',
], [
  ({}, {'condition': '', 'ordering': []}),
  ({'condition': ''}, {'condition': '', 'ordering': []}),
  ({'condition': 'price < 123'}, {'condition': 'price < 123', 'ordering': []}),
  ({'ordering': '-code'}, {'condition': '', 'ordering': ['-code']}),
  ({'ordering': '-code,price'}, {'condition': '', 'ordering': ['-code', 'price']}),
  ({'condition': 'price < 1234', 'ordering': 'code,-price'}, {'condition': 'price < 1234', 'ordering': ['code', '-price']}),
], ids=[
  'empty-param',
  'condition-data-with-empty-data',
  'condition-of-valid-data',
  'ordering-of-valid-data',
  'ordering-of-multi-valid-data',
  'valid-both-data',
])
def test_init_method_of_search_form(params, exacts):
  form = forms.StockSearchForm(data=params)
  is_valid = form.is_valid()
  condition = form.cleaned_data['condition']
  ordering = form.cleaned_data['ordering']
  exact_cond = exacts['condition']
  exact_order = exacts['ordering']

  assert is_valid
  assert condition == exacts['condition']
  assert all([estimated == _exact for estimated, _exact in zip(ordering, exact_order)])

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.parametrize([
  'params',
  'is_valid',
], [
  ({'condition': 'price < 100'}, True),
  ({'condition': 'price < 100\nand\ncode=="cone"'}, True),
  ({'condition': ''}, True),
  ({'condition': 'code<"1200"'}, False),
], ids=[
  'valid-inputs',
  'valid-inputs-with-return-code',
  'empty-input',
  'invalid-inputs',
])
def test_stock_search_form_validation(params, is_valid):
  form = forms.StockSearchForm(data=params)

  assert form.is_valid() == is_valid

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.parametrize([
  'params',
  'is_valid',
], [
  ({'target': 'code', 'compop': '==', 'inputs': '"hoge"', 'condition': '', 'ordering': 'name'}, True),
  ({'target': 'code', 'compop': '==', 'inputs': '"hoge"', 'condition': ''}, True),
  ({'target': 'code', 'compop': '==', 'inputs': '"hoge"'}, True),
  ({'target': 'code', 'compop': '=='}, True),
  ({'target': 'code'}, True),
  ({}, True),
  ({'no-field': 'hogehoge'}, True),
], ids=[
  'send-all-fields',
  'send-target-compop-inputs-condition',
  'send-target-compop-inputs',
  'send-target-compop',
  'send-target-only',
  'send-empty-data',
  'ignore-field',
])
def test_target_field_data_of_stock_search_form(params, is_valid):
  form = forms.StockSearchForm(data=params)

  assert form.is_valid() == is_valid

@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'params',
  'indices',
  'exact_valid',
], [
  ({'condition': 'price < 500', 'ordering': 'price'}, [0, 1, 2], True),
  ({'condition': 'price < 500'}, [0, 2, 1], True),
  ({'condition': 'price < 500 and code == "600"'}, [1], True),
  ({'condition': 'price < 500\n and\n code == "600"'}, [1], True),
  ({}, [0, 2, 4, 1, 3], True),
  ({'condition': ''}, [0, 2, 4, 1, 3], True),
  ({'ordering': ''}, [0, 2, 4, 1, 3], True),
  ({'condition': 'price + 100 < 5000', 'ordering': 'price'}, [0, 1, 2, 3, 4], False),
], ids=[
  'set-condition-and-order',
  'set-condition',
  'set-multi-conditions',
  'set-multi-conditions-with-return-code',
  'set-no-fields',
  'empty-condition',
  'empty-ordering',
  'invalid-condition',
])
def test_get_queryset_with_condition_method_of_stock_search_form(params, indices, exact_valid):
  industry = factories.IndustryFactory()
  stocks = [
    factories.StockFactory(code='100', price=100, industry=industry),
    factories.StockFactory(code='600', price=250, industry=industry),
    factories.StockFactory(code='200', price=300, industry=industry),
    factories.StockFactory(code='800', price=500, industry=industry),
    factories.StockFactory(code='400', price=750, industry=industry),
  ]
  form = forms.StockSearchForm(data=params)
  is_valid = form.is_valid()
  qs = form.get_queryset_with_condition()
  expected = [stocks[idx] for idx in indices]

  assert is_valid == exact_valid
  assert len(expected) == qs.count()
  assert all([record.pk == exact.pk for record, exact in zip(qs, expected)])