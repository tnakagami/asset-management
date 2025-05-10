import pytest
from datetime import datetime, timezone
from stock.models import PurchasedStock, Stock
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

  with pytest.raises(forms.ValidationError) as ex:
    _ = field.to_python(_vals[arg_idx])

  assert 'Select a valid choice' in str(ex.value)

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