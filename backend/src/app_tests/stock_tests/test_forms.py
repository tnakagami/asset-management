import pytest
import ast
import json
import urllib.parse
import sys
from functools import wraps
from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
from django.db.utils import IntegrityError
from django.contrib.auth import get_user_model
from django_celery_beat.models import PeriodicTask
from stock import forms, models
from app_tests import factories, get_date, BaseTestUtils

UserModel = get_user_model()

@pytest.fixture(scope='module')
def get_sample_stocks(django_db_blocker):
  with django_db_blocker.unblock():
    stocks = factories.StockFactory.create_batch(3)

  return stocks

@pytest.mark.stock
@pytest.mark.form
class TestGlobalFunctions:
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
  def test_check_bool_converter(self, value, expected):
    estimated = forms.bool_converter(value)

    assert estimated == expected

# ========
# CashForm
# ========
@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
class TestCashForm:
  @pytest.mark.parametrize([
    'params',
    'is_valid',
  ], [
    ({'balance': 10,  'registered_date': get_date((2022, 7, 3))}, True),
    ({'balance':  0,  'registered_date': get_date((2022, 7, 3))}, True),
    ({'balance': -1,  'registered_date': get_date((2022, 7, 3))}, False),
    ({                'registered_date': get_date((2022, 7, 3))}, False),
    ({'balance': 'a', 'registered_date': get_date((2022, 7, 3))}, False),
    ({'balance': 10,  'registered_date':              '123456'}, False),
    ({'balance': 10,  'registered_date':                 'abc'}, False),
    ({'balance': 10,                                          }, False),
    ({                                                        }, False),
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
  def test_cash_form(self, get_user, params, is_valid):
    user = get_user
    form = forms.CashForm(user=user, data=params)

    assert form.is_valid() == is_valid

# ==================
# PurchasedStockForm
# ==================
@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
class TestPurchasedStockForm:
  @pytest.mark.parametrize([
    'exist_stock',
    'kwargs',
    'is_valid',
  ], [
    (True,  {'price':  10, 'purchase_date': get_date((2022, 7, 3)), 'count':   5, 'has_been_sold': False}, True),
    (True,  {'price':   0, 'purchase_date': get_date((2022, 7, 3)), 'count':   5, 'has_been_sold': False}, True),
    (True,  {'price':  10, 'purchase_date': get_date((2022, 7, 3)), 'count':   0, 'has_been_sold': False}, True),
    (True,  {'price':   7, 'purchase_date': get_date((2022, 7, 3)), 'count':   2, 'has_been_sold': True},  True),
    (False, {'price':  10, 'purchase_date': get_date((2022, 7, 3)), 'count':   5, 'has_been_sold': False}, False),
    (True,  {'price':  -1, 'purchase_date': get_date((2022, 7, 3)), 'count':   5, 'has_been_sold': False}, False),
    (True,  {'price': 'a', 'purchase_date': get_date((2022, 7, 3)), 'count':   5, 'has_been_sold': False}, False),
    (True,  {'price':  10, 'purchase_date':               '123456', 'count':   5, 'has_been_sold': False}, False),
    (True,  {'price':  10, 'purchase_date':                  'abc', 'count':   5, 'has_been_sold': False}, False),
    (True,  {'price':  10, 'purchase_date': get_date((2022, 7, 3)), 'count':  -1, 'has_been_sold': False}, False),
    (True,  {'price':  10, 'purchase_date': get_date((2022, 7, 3)), 'count': 'a', 'has_been_sold': False}, False),
    (True,  {              'purchase_date': get_date((2022, 7, 3)), 'count':   5, 'has_been_sold': False}, False),
    (True,  {'price':  10,                                          'count':   5, 'has_been_sold': False}, False),
    (True,  {'price':  10, 'purchase_date': get_date((2022, 7, 3)),               'has_been_sold': False}, False),
    (False, {                                                                                           }, False),
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
  def test_purchased_stock_form(self, get_user, get_sample_stocks, exist_stock, kwargs, is_valid):
    user = get_user
    instance = get_sample_stocks[0]
    params = {}
    # Check stock status
    if exist_stock:
      params['stock'] = instance.pk
    # Set rest params
    for key, val in kwargs.items():
      params[key] = val
    form = forms.PurchasedStockForm(user=user, data=params)

    assert form.is_valid() == is_valid

  def test_check_invalid_stock_pk(self, get_user):
    user = get_user
    params = {
      'stock': 0,
      'price': 10,
      'purchase_date': get_date((2022, 7, 3)),
      'count': 5,
    }
    form = forms.PurchasedStockForm(user=user, data=params)
    is_valid = form.is_valid()

    assert not is_valid
    assert form.fields['stock'].widget._has_error

  def test_stock_field_doesnot_have_error(self, mocker, get_user, get_sample_stocks):
    user = get_user
    stock = get_sample_stocks[0]
    instance = factories.PurchasedStockFactory(user=user, stock=stock)
    params = {
      'stock': stock.pk,
      'price': 10,
      'purchase_date': get_date((2022, 7, 3)),
      'count': 5,
      'has_been_sold': False,
    }
    form = forms.PurchasedStockForm(user=user, data=params)
    form.fields['stock'].error_messages = {}
    is_valid = form.is_valid()

    assert is_valid
    assert len(form.fields['stock'].error_messages) == 0

  def test_check_valid_update_queryset(self, get_user, get_sample_stocks):
    user = get_user
    stocks = get_sample_stocks
    # Create instances
    instances = [
      factories.PurchasedStockFactory(user=user, stock=stock)
      for stock in stocks
    ]
    params = {
      'stock': instances[1].stock.pk,
      'price': 10,
      'purchase_date': get_date((2022, 7, 3)),
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

  def test_check_invalid_update_queryset(self, get_user, get_sample_stocks):
    user = get_user
    stock = get_sample_stocks[0]
    instance = factories.PurchasedStockFactory(user=user, stock=stock)
    params = {
      'stock': stock.pk,
      'price': 10,
      'purchase_date': get_date((2022, 7, 3)),
      'count': 5,
    }
    form = forms.PurchasedStockForm(user=user, data=params)

    with pytest.raises(models.PurchasedStock.DoesNotExist) as ex:
      form.update_queryset(pk=0)

    assert 'matching query does not exist' in str(ex.value)

# ===========================
# UploadCsvPurchasedStockForm
# ===========================
@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
class TestUploadCsvPurchasedStockForm:
  def test_check_filtering(self):
    data = ['a', '', 'c', '3']
    form = forms.UploadCsvPurchasedStockForm()
    row = form.filtering(data)

    assert row == ['a', 'c', '3']

  def test_valid_form_input(self, mocker, get_csvfile_form_param):
    params, files = get_csvfile_form_param
    form = forms.UploadCsvPurchasedStockForm(data=params, files=files)
    mocker.patch.object(form, 'length_checker', return_value=True)
    mocker.patch.object(form, 'extractor', side_effect=lambda rows: rows)
    mocker.patch.object(form, 'record_checker', return_value=None)
    is_valid = form.is_valid()

    assert is_valid
    assert form.valid_data is not None

  def test_invalid_form_input(self, mocker, get_err_form_param_with_csvfile):
    params, files, configs, err_msg = get_err_form_param_with_csvfile
    form = forms.UploadCsvPurchasedStockForm(data=params, files=files)
    # Mock specific object
    for target, kwargs in configs.items():
      mocker.patch.object(form, target, **kwargs)
    # Validate form
    is_valid = form.is_valid()

    assert not is_valid
    assert err_msg in str(form.errors)

  def test_failed_to_read_csv_file(self, mocker, get_single_csvfile_form_data):
    mocker.patch('stock.forms.TextIOWrapper', side_effect=UnicodeDecodeError('cp932',b'',1,1,''))
    err_msg = 'Failed to decode in line 0 (Encoding: cp932).'
    # Create form
    params, files = get_single_csvfile_form_data
    form = forms.UploadCsvPurchasedStockForm(data=params, files=files)
    is_valid = form.is_valid()

    assert not is_valid
    assert err_msg in str(form.errors)

  def test_default_valid_data(self):
    form = forms.UploadCsvPurchasedStockForm()
    data = form.get_data()

    assert data is None

  def test_valid_registration(self, mocker, get_single_csvfile_form_data):
    stocks = factories.StockFactory.create_batch(2)
    records = [
      (stocks[0].code, '2020-01-02 00:00:00+00:00', '1100.3', '100'),
      (stocks[1].code, '2020-01-03 00:00:00+00:00', '1101.3', '200'),
    ]
    mocker.patch('stock.forms.UploadCsvPurchasedStockForm.validate_csv_file', return_value=None)
    mocker.patch('stock.forms.UploadCsvPurchasedStockForm.get_data', return_value=records)
    # Create form
    user = factories.UserFactory()
    params, files = get_single_csvfile_form_data
    form = forms.UploadCsvPurchasedStockForm(data=params, files=files)
    is_valid = form.is_valid()
    instances = form.register(user)
    qs = user.purchased_stocks.all()
    expected_code, expected_date, expected_price, expected_count = records[1]
    pstock = qs.get(stock__code=expected_code)

    assert is_valid
    assert not form.has_error(NON_FIELD_ERRORS)
    assert len(qs) == len(instances)
    assert models.convert_timezone(pstock.purchase_date, is_string=True) == expected_date.replace(' ', 'T')
    assert abs(float(pstock.price) - float(expected_price)) < 1e-2
    assert pstock.count == int(expected_count)

  @pytest.mark.parametrize([
    'exception_class',
    'err_msg',
  ], [
    (IntegrityError, 'Include invalid records. Please check the detail:'),
    (Exception, 'Unexpected error occurred:'),
  ], ids=['has-integrity-error', 'has-exception'])
  def test_raise_exception_in_bulk_create(self, mocker, get_single_csvfile_form_data, exception_class, err_msg):
    mocker.patch('stock.forms.UploadCsvPurchasedStockForm.validate_csv_file', return_value=None)
    mocker.patch('stock.forms.UploadCsvPurchasedStockForm.get_data', return_value=[1])
    mocker.patch('stock.models.PurchasedStock.from_list', return_value=[2])
    mocker.patch('stock.models.PurchasedStock.objects.bulk_create', side_effect=exception_class('Invalid data'))
    # Create form
    user = factories.UserFactory()
    params, files = get_single_csvfile_form_data
    form = forms.UploadCsvPurchasedStockForm(data=params, files=files)
    is_valid = form.is_valid()
    instances = form.register(user)

    assert is_valid
    assert form.has_error(NON_FIELD_ERRORS)
    assert err_msg in str(form.non_field_errors())
    assert len(instances) == 0

# =============================
# DownloadCsvPurchasedStockForm
# =============================
@pytest.mark.stock
@pytest.mark.form
class TestDownloadCsvPurchasedStockForm:
  @pytest.mark.parametrize([
    'params',
  ], [
    ({}, ),
    ({'filename': '',}, ),
    ({'filename': 'hoge'}, ),
    ({'filename': '日本語'}, ),
  ], ids=[
    'no-inputs',
    'empty-data',
    'valid-data',
    'use-multi-byte-filename',
  ])
  def test_check_validation(self, params):
    form = forms.DownloadCsvPurchasedStockForm(data=params)

    assert form.is_valid()

  @pytest.mark.parametrize([
    'params',
  ], [
    ({'filename': '1'*129,}, ),
  ], ids=[
    'filename-is-too-long',
  ])
  def test_check_invalid_pattern(self, params):
    form = forms.DownloadCsvPurchasedStockForm(data=params)

    assert not form.is_valid()

  @pytest.mark.parametrize([
    'params',
    'arg_fname',
  ], [
    ({'filename': 'hoge'}, 'hoge'),
    ({'filename': '.csv'}, ''),
    ({'filename': 'hoge.csv'}, 'hoge'),
  ], ids=[
    'valid-pattern',
    'valid-only-extension-pattern',
    'include-extension',
  ])
  def test_check_create_response_kwargs(self, mocker, params, arg_fname):
    kwargs_mock = mocker.patch('stock.models.PurchasedStock.create_response_kwargs', return_value={})
    mock_user = mocker.Mock(spec=UserModel)
    form = forms.DownloadCsvPurchasedStockForm(data=params)
    is_valid = form.is_valid()
    _ = form.create_response_kwargs(mock_user)
    args, _ = kwargs_mock.call_args
    fname, _ = args

    assert is_valid
    assert fname == arg_fname

# ========================
# CustomModelDatalistField
# ========================
@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
class TestCustomModelDatalistField:
  @pytest.mark.parametrize([
    'arg_idx',
    'checker',
  ], [
    (0, lambda ret: isinstance(ret, models.Stock)),
    (1, lambda ret: isinstance(ret, models.Stock)),
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
  def test_check_valid_custom_modeldatalist_field(self, get_sample_stocks, arg_idx, checker):
    stocks = get_sample_stocks
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
    field = forms.CustomModelDatalistField(queryset=models.Stock.objects.all())
    ret = field.to_python(value)

    assert checker(ret)

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
  def test_check_invalid_custom_modeldatalist_field(self, get_sample_stocks, arg_idx):
    stocks = get_sample_stocks
    _vals = [
      [2],
      -1,
      0,
    ]
    field = forms.CustomModelDatalistField(queryset=models.Stock.objects.all())

    with pytest.raises(ValidationError) as ex:
      _ = field.to_python(_vals[arg_idx])

    assert 'Select a valid choice' in str(ex.value)

# ============
# SnapshotForm
# ============
@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
class TestSnapshotForm:
  @pytest.mark.parametrize([
    'params',
    'is_valid',
  ], [
    ({'title': 'sample', 'priority': 99, 'start_date': get_date((2022, 7, 2)), 'end_date': get_date((2022, 7, 28))}, True),
    ({'title': 'sample', 'priority': 99,                                       'end_date': get_date((2022, 7, 28))}, True),
    ({'title': 'sample', 'priority': 99, 'start_date': get_date((2022, 7, 2))                                     }, False),
    ({                   'priority': 99, 'start_date': get_date((2022, 7, 2)), 'end_date': get_date((2022, 7, 28))}, False),
    ({'title': 'sample',                 'start_date': get_date((2022, 7, 2)), 'end_date': get_date((2022, 7, 28))}, False),
    ({'title': 'sample', 'priority': 99, 'start_date':       'abc',            'end_date': get_date((2022, 7, 28))}, False),
    ({'title': 'sample', 'priority': 99, 'start_date':       '123',            'end_date': get_date((2022, 7, 28))}, False),
    ({'title': 'sample', 'priority': 99, 'start_date': get_date((2022, 7, 2)), 'end_date':                   'abc'}, False),
    ({'title': 'sample', 'priority': 99, 'start_date': get_date((2022, 7, 2)), 'end_date':                   '123'}, False),
    ({                                                                                                            }, False),
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
  def test_snapshot_form(self, get_user, params, is_valid):
    user = get_user
    form = forms.SnapshotForm(user=user, data=params)

    assert form.is_valid() == is_valid

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
  def test_save_method(self, get_user, forced_update, commit, output_dlen, record_dlen):
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
      'start_date': get_date((2022, 7, 2)),
      'end_date': get_date((2022, 7, 28)),
      'forced_update': forced_update,
    }
    form = forms.SnapshotForm(user=user, data=params)
    form.instance = instance
    is_valid = form.is_valid()
    output = form.save(commit=commit)
    estimated = models.Snapshot.objects.get(pk=instance.pk)
    detail_output = json.loads(output.detail)
    detail_estimated = json.loads(estimated.detail)

    assert is_valid
    assert len(detail_output) == output_dlen
    assert len(detail_estimated) == record_dlen

# ============================
# UploadJsonFormatSnapshotForm
# ============================
@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
class TestUploadJsonFormatSnapshotForm:
  def test_valid_input_pattern(self, get_jsonfile_form_param):
    user = factories.UserFactory()
    params, files = get_jsonfile_form_param
    form = forms.UploadJsonFormatSnapshotForm(user=user, data=params, files=files)
    is_valid = form.is_valid()

    assert is_valid

  @pytest.fixture(params=[
    ('no-encoding', '.json'),
    ('no-file', '.json'),
    ('invalid-suffix', '.txt'),
  ], ids=[
    'without-encoding',
    'without-jsonfile',
    'invalid-suffix',
  ])
  def get_invalid_form_param(self, request, get_form_param_with_json_fd):
    key, suffix = request.param
    # Setup temporary file
    tmp_fp, json_file, params, files = get_form_param_with_json_fd('utf-8', suffix)
    err_msg = 'This field is required'
    # Setup form data
    if key == 'no-encoding':
      del params['encoding']
    elif key == 'no-file':
      del files['json_file']
    elif key == 'invalid-suffix':
      err_msg = 'The extention has to be &quot;.json&quot;.'

    yield params, files, err_msg

    # Post-process
    json_file.close()
    tmp_fp.close()

  def test_invalid_field_data(self, get_invalid_form_param):
    user = factories.UserFactory()
    params, files, err_msg = get_invalid_form_param
    form = forms.UploadJsonFormatSnapshotForm(user=user, data=params, files=files)
    is_valid = form.is_valid()

    assert not is_valid
    assert err_msg in str(form.errors)

  @pytest.fixture
  def get_params_for_register(self, get_form_param_with_json_fd):
    tmp_fp, json_file, params, files = get_form_param_with_json_fd('utf-8')

    yield params, files

    # Post-process
    json_file.close()
    tmp_fp.close()

  def test_check_register_method(settings, mocker, get_params_for_register):
    user = factories.UserFactory()
    mocker.patch('stock.forms.UploadJsonFormatSnapshotForm.clean', return_value=None)
    valid_data = {
      'title': 'dummy-data-for-ujf-ss',
      'detail': {
        'cash': {
          'balance': 7890,
          'registered_date': '2000-01-02',
        },
        'purchased_stocks': [{
          'stock': {
            'hoge': 'foo',
          },
          'price': 950.4,
          'purchase_date': '2001-03-12',
          'count': 123,
        }],
      },
      'priority': 98,
      'start_date': '1999-12-11T00:00:00+09:00',
      'end_date': '2100-12-31T00:00:00+09:00',
    }
    # Create form
    params, files = get_params_for_register
    form = forms.UploadJsonFormatSnapshotForm(user=user, data=params, files=files)
    is_valid = form.is_valid()
    form.valid_data = valid_data
    instance = form.register()
    output_detail = json.loads(instance.detail)

    assert is_valid
    assert instance.title == valid_data['title']
    assert output_detail == valid_data['detail']
    assert instance.start_date == valid_data['start_date']
    assert instance.end_date == valid_data['end_date']
    assert instance.priority == valid_data['priority']

  def test_invalid_clean_method(self, get_err_form_param_with_jsonfile):
    user = factories.UserFactory()
    params, files, err_msg = get_err_form_param_with_jsonfile
    form = forms.UploadJsonFormatSnapshotForm(user=user, data=params, files=files)
    is_valid = form.is_valid()

    assert not is_valid
    assert err_msg in str(form.errors)

# ===========================
# PeriodicTaskForSnapshotForm
# ===========================
@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
class TestPeriodicTaskForSnapshotForm:
  @pytest.fixture(scope='class')
  def get_pseudo_snapshot(self, django_db_blocker):
    with django_db_blocker.unblock():
      user = factories.UserFactory()
      _ = factories.CashFactory.create_batch(2, user=user)
      _ = factories.PurchasedStockFactory.create_batch(3, user=user)
      _ = factories.SnapshotFactory(user=user)
      _ = factories.CashFactory.create_batch(3, user=user)
      _ = factories.PurchasedStockFactory.create_batch(2, user=user)
      snapshot = factories.SnapshotFactory(user=user)

    return user, snapshot

  @pytest.fixture
  def pseudo_periodic_task_params(self, get_pseudo_snapshot):
    user, snapshot = get_pseudo_snapshot
    # It is the pattern of  `schedule_type` == `every-day`
    params = {
      'name': 'hoge',
      'enabled': True,
      'snapshot': snapshot.pk,
      'schedule_type': 'every-day',
      'config': {'minute': 23, 'hour': 13},
    }

    return user, params

  def test_check_init_func(self, get_user):
    user = get_user
    form = forms.PeriodicTaskForSnapshotForm(user=user)

    assert form.default_schedule == 'every-day'
    assert form.schedule_restriction['every-day'] == ['minute', 'hour']
    assert form.schedule_restriction['every-week'] == ['minute', 'hour', 'day_of_week']
    assert form.schedule_restriction['every-month'] == ['minute', 'hour', 'day_of_month']

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
  def test_check_update_initial(self, get_user, param_cron, callback, expected_schedule_type):
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

  def test_unexpected_kwargs(self, get_user):
    user = get_user
    task = factories.PeriodicTaskFactory(kwargs=json.dumps({'user_pk': user.pk, 'snapshot_pk': 0}))
    form = forms.PeriodicTaskForSnapshotForm(user=user)
    form.update_initial(task)
    instance = form.fields['snapshot'].initial

    assert instance is None

  def test_basic_pattern(self, pseudo_periodic_task_params):
    user, params = pseudo_periodic_task_params
    form = forms.PeriodicTaskForSnapshotForm(user=user, data=params)

    assert form.is_valid()

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
  def test_check_save_method(self, pseudo_periodic_task_params, commit, expected_count):
    user, params = pseudo_periodic_task_params
    ss_pk = params['snapshot']
    form = forms.PeriodicTaskForSnapshotForm(user=user, data=params)
    is_valid = form.is_valid()
    instance = form.save(commit=commit)
    kwargs = json.dumps({'user_pk': user.pk, 'snapshot_pk': ss_pk})
    count = PeriodicTask.objects.filter(kwargs__contains=kwargs).count()
    snapshot = models.Snapshot.objects.get(pk=ss_pk)

    assert is_valid
    assert count == expected_count
    assert instance.task == 'stock.tasks.update_specific_snapshot'
    assert instance.description == snapshot.title

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
  def test_customized_valid_pattern(self, pseudo_periodic_task_params, kwargs_to_update):
    user, params = pseudo_periodic_task_params
    params.update(kwargs_to_update)
    form = forms.PeriodicTaskForSnapshotForm(user=user, data=params)

    assert form.is_valid()

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
  def test_invalid_pattern(self, pseudo_periodic_task_params, kwargs_to_update, delete_list, err_msg):
    user, params = pseudo_periodic_task_params
    params.update(kwargs_to_update)

    for key in delete_list:
      del params[key]
    form = forms.PeriodicTaskForSnapshotForm(user=user, data=params)
    is_valid = form.is_valid()

    assert not is_valid
    assert err_msg in str(form.errors)

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
  def test_invalid_crontab(self, pseudo_periodic_task_params, schedule_type, kwargs_to_update):
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

# ===============
# StockSearchForm
# ===============
@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
class TestStockSearchForm(BaseTestUtils):
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
  def test_init_method(self, params, exacts):
    form = forms.StockSearchForm(data=params)
    is_valid = form.is_valid()
    condition = form.cleaned_data['condition']
    ordering = form.cleaned_data['ordering']
    exact_cond = exacts['condition']
    exact_order = exacts['ordering']

    assert is_valid
    assert condition == exacts['condition']
    assert all([estimated == _exact for estimated, _exact in zip(ordering, exact_order)])

  def test_invalid_ordering_type(self):
    param = {'ordering': 'price-code'}
    form = forms.StockSearchForm(data=param)
    is_valid = form.is_valid()

    assert not is_valid

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
  def test_input_validation(self, params, is_valid):
    form = forms.StockSearchForm(data=params)

    assert form.is_valid() == is_valid

  def test_no_input_arguments(self):
    form = forms.StockSearchForm()

    assert form.is_valid()

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
  def test_target_field_data(self, params, is_valid):
    form = forms.StockSearchForm(data=params)

    assert form.is_valid() == is_valid

  @pytest.fixture(scope='class')
  def get_pseudo_stocks(self, django_db_blocker):
    with django_db_blocker.unblock():
      industry = factories.IndustryFactory()
      stocks = [
        factories.StockFactory(code='100', price=100, industry=industry),
        factories.StockFactory(code='600', price=250, industry=industry),
        factories.StockFactory(code='200', price=300, industry=industry),
        factories.StockFactory(code='800', price=500, industry=industry),
        factories.StockFactory(code='400', price=750, industry=industry),
      ]

    return stocks

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
  def test_check_get_queryset_with_condition(self, get_pseudo_stocks, mocker, params, indices, exact_valid):
    stocks = get_pseudo_stocks
    queryset = models.Stock.objects.filter(pk__in=self.get_pks(stocks))
    mocker.patch('stock.models.StockManager.get_queryset', return_value=queryset)
    form = forms.StockSearchForm(data=params)
    is_valid = form.is_valid()
    qs = form.get_queryset_with_condition()
    expected = [stocks[idx] for idx in indices]

    assert is_valid == exact_valid
    assert len(expected) == qs.count()
    assert all([record.pk == exact.pk for record, exact in zip(qs, expected)])

# ===========================
# PurchasedStockFilteringForm
# ===========================
@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
class TestPurchasedStockFilteringForm(BaseTestUtils):
  @pytest.mark.parametrize([
    'params',
    'exacts',
  ], [
    ({}, {'condition': ''}),
    ({'condition': ''}, {'condition': ''}),
    ({'condition': 'price < 123'}, {'condition': 'price < 123'}),
  ], ids=[
    'empty-param',
    'empty-condition-data',
    'valid-condition-data',
  ])
  def test_init_method(self, params, exacts):
    form = forms.PurchasedStockFilteringForm(data=params)
    is_valid = form.is_valid()
    condition = form.cleaned_data['condition']
    exact_cond = exacts['condition']

    assert is_valid
    assert condition == exacts['condition']

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
  def test_input_validation(self, params, is_valid):
    form = forms.PurchasedStockFilteringForm(data=params)

    assert form.is_valid() == is_valid

  def test_no_input_arguments(self):
    form = forms.PurchasedStockFilteringForm()

    assert form.is_valid()

  @pytest.mark.parametrize([
    'params',
    'is_valid',
  ], [
    ({'target': 'code', 'compop': '==', 'inputs': '"hoge"', 'condition': ''}, True),
    ({'target': 'code', 'compop': '==', 'inputs': '"hoge"'}, True),
    ({'target': 'code', 'compop': '=='}, True),
    ({'target': 'code'}, True),
    ({}, True),
    ({'no-field': 'hogehoge'}, True),
  ], ids=[
    'send-target-compop-inputs-condition',
    'send-target-compop-inputs',
    'send-target-compop',
    'send-target-only',
    'send-empty-data',
    'ignore-field',
  ])
  def test_target_field_data(self, params, is_valid):
    form = forms.PurchasedStockFilteringForm(data=params)

    assert form.is_valid() == is_valid

  @pytest.fixture(scope='class')
  def get_pseudo_purchased_stocks(self, django_db_blocker):
    with django_db_blocker.unblock():
      user = factories.UserFactory()
      industry = factories.IndustryFactory()
      stock1 = factories.StockFactory(code='001abc', price=1000, industry=industry)
      stock2 = factories.StockFactory(code='002xyz', price=2000, industry=industry)
      _ = factories.LocalizedStockFactory(name='hogehoge', stock=stock1)
      _ = factories.LocalizedStockFactory(name='foobar', stock=stock2)
      purchased_stocks = [
        factories.PurchasedStockFactory(user=user, stock=stock1, price=999,  count=1,   purchase_date=get_date((2020, 1, 1))),
        factories.PurchasedStockFactory(user=user, stock=stock1, price=1001, count=1,   purchase_date=get_date((2022, 6, 7))),
        factories.PurchasedStockFactory(user=user, stock=stock2, price=1999, count=1,   purchase_date=get_date((2019, 3, 4))),
        factories.PurchasedStockFactory(user=user, stock=stock2, price=2002, count=1,   purchase_date=get_date((2020, 1, 1))),
        factories.PurchasedStockFactory(user=user, stock=stock2, price=2003, count=100, purchase_date=get_date((2021, 2, 3))),
      ]

    return user, purchased_stocks

  @pytest.mark.parametrize([
    'params',
    'indices',
    'exact_valid',
  ], [
    ({'condition': 'price < 1000'}, [0], True),
    ({'condition': 'count == 1'}, [1, 0, 3, 2], True),
    ({'condition': 'count == 1 and code == "002xyz"'}, [3, 2], True),
    ({'condition': 'count == 1\n and\n diff < 0'}, [1, 3], True),
    ({}, [1, 4, 0, 3, 2], True),
    ({'condition': ''}, [1, 4, 0, 3, 2], True),
    ({'condition': 'price + 100 < 5000'}, [1, 4, 0, 3, 2], False),
  ], ids=[
    'set-condition-with-single-match',
    'set-condition-with-multiple-matches',
    'set-multi-conditions',
    'set-multi-conditions-with-return-code',
    'set-no-fields',
    'empty-condition',
    'invalid-condition',
  ])
  def test_check_get_queryset_with_condition(self, get_pseudo_purchased_stocks, params, indices, exact_valid):
    user, purchased_stocks = get_pseudo_purchased_stocks
    form = forms.PurchasedStockFilteringForm(data=params)
    is_valid = form.is_valid()
    qs = form.get_queryset_with_condition(user)
    expected = [purchased_stocks[idx] for idx in indices]

    assert is_valid == exact_valid
    assert len(expected) == qs.count()
    assert all([record.pk == exact.pk for record, exact in zip(qs, expected)])

# =================
# StockDownloadForm
# =================
@pytest.mark.stock
@pytest.mark.form
class TestStockDownloadForm:
  @pytest.mark.parametrize([
    'params',
  ], [
    ({}, ),
    ({'filename': '', 'condition': '', 'ordering': ''}, ),
    ({'filename': 'hoge', 'condition': 'price > 0', 'ordering': 'code'}, ),
    ({'filename': 'hoge', 'condition': 'price in 0', 'ordering': 'code'}, ),
    ({'filename': 'hoge', 'condition': 'price > 0', 'ordering': 'xxx'}, ),
    ({'filename': '日本語', 'condition': 'price > 0', 'ordering': 'code'}, ),
    ({'filename': 'hoge', 'condition': '2'*1025, 'ordering': 'code', 'allowed_long_condition': True}, ),
  ], ids=[
    'no-inputs',
    'empty-data',
    'valid-data',
    'invalid-condition',
    'invalid-ordering',
    'use-multi-byte-filename',
    'allowd-long-condition',
  ])
  def test_check_validation(self, params):
    form = forms.StockDownloadForm(data=params)

    assert form.is_valid()

  @pytest.mark.parametrize([
    'params',
  ], [
    ({'filename': '1'*129, 'condition': 'price > 0', 'ordering': 'code'}, ),
    ({'filename': 'hoge', 'condition': '2'*1025, 'ordering': 'code'}, ),
    ({'filename': 'hoge', 'condition': 'price > 0', 'ordering': '3'*1025}, ),
  ], ids=[
    'filename-is-too-long',
    'condition-is-too-long',
    'ordering-is-too-long',
  ])
  def test_check_invalid_pattern(self, params):
    form = forms.StockDownloadForm(data=params)

    assert not form.is_valid()

  @pytest.mark.parametrize([
    'condition',
    'is_allowd',
    'is_valid',
  ], [
    ('123', False, True),
    ('1'*1025, False, False),
    ('1'*1025, True, True),
  ], ids=[
    'short-condition',
    'invalid-long-condition',
    'allow-long-condition',
  ])
  def test_check_clean_method(self, condition, is_allowd, is_valid):
    err_msg = 'Condition is too long. Please enter more short condition.'
    params = {
      'condition': condition,
      'allowed_long_condition': is_allowd,
    }
    form = forms.StockDownloadForm(data=params)
    validation_result = form.is_valid()
    exact = '' if is_valid else err_msg
    err = form.errors.get('condition', '')

    assert validation_result == is_valid
    assert exact in err

  @pytest.mark.parametrize([
    'params',
  ], [
    ({'condition': 'price > 100', 'ordering': 'code'}, ),
    ({'condition': 'price > 100', 'ordering': ''}, ),
    ({'condition': '', 'ordering': 'code'}, ),
  ], ids=[
    'both-queries-exist',
    'only-condition',
    'only-ordering',
  ])
  def test_check_query_string(self, params):
    params.update({'filename': 'hoge'})
    form = forms.StockDownloadForm(data=params)
    is_valid = form.is_valid()
    query_string = form.get_query_string()
    expected = urllib.parse.quote('condition={}&ordering={}'.format(params['condition'], params['ordering']))

    assert is_valid
    assert query_string == expected

  @pytest.mark.parametrize([
    'params',
    'arg_fname',
    'arg_tree',
    'arg_order',
  ], [
    ({'filename': 'hoge.csv', 'condition': 'price > 1000', 'ordering': '-code'}, 'hoge', 'price > 1000', ['-code']),
    ({'filename': '.csv', 'condition': 'price > 1000', 'ordering': '-code'}, '', 'price > 1000', ['-code']),
    ({'filename': 'hoge', 'condition': 'name in "foo"', 'ordering': 'yyy,price,xxx'}, 'hoge', 'name in "foo"', [models.StockOrderingTypes.CODE_ASC.value]),
    ({'filename': 'hoge', 'condition': 'industry_name in "bar"', 'ordering': 'code,price'}, 'hoge', 'industry_name in "bar"', ['code', 'price']),
    ({'filename': 'hoge', 'condition': 'price > 10', 'ordering': 'zzz,www'}, 'hoge', 'price > 10', [models.StockOrderingTypes.CODE_ASC.value]),
  ], ids=[
    'valid-pattern',
    'valid-only-extension-pattern',
    'include-invalid-orderings',
    'input-multiple-orderings',
    'invalid-all-orderings',
  ])
  def test_check_create_response_kwargs(self, mocker, params, arg_fname, arg_tree, arg_order):
    kwargs_mock = mocker.patch('stock.models.Stock.create_response_kwargs', return_value={})
    form = forms.StockDownloadForm(data=params)
    is_valid = form.is_valid()
    _ = form.create_response_kwargs()
    args, _ = kwargs_mock.call_args
    fname, tree, order = args

    assert is_valid
    assert fname == arg_fname
    assert ast.dump(tree) == ast.dump(ast.parse(arg_tree, mode='eval'))
    assert order == arg_order

  @pytest.mark.parametrize([
    'params',
    'expected_fname',
  ], [
    ({'condition': '', 'ordering': '', 'filename': '.csv'}, ''),
    ({'condition': 'price in "NG"', 'ordering': '', 'filename': '.csv'}, ''),
    ({}, ''),
  ], ids=[
    'empty-condition',
    'invalid-condition',
    'empty-params',
  ])
  def test_specific_patterns_in_create_response_kwargs(self, mocker, params, expected_fname):
    kwargs_mock = mocker.patch('stock.models.Stock.create_response_kwargs', return_value={})
    form = forms.StockDownloadForm(data=params)
    is_valid = form.is_valid()
    _ = form.create_response_kwargs()
    args, _ = kwargs_mock.call_args
    fname, tree, order = args

    assert fname == expected_fname
    assert tree is None
    assert order == [models.StockOrderingTypes.CODE_ASC.value]

# =================
# StockScreenerForm
# =================
@pytest.mark.stock
@pytest.mark.form
@pytest.mark.django_db
class TestStockScreenerForm:
  @pytest.mark.parametrize([
    'field_name',
    'choices',
    'attrs',
  ], [
    ('target', models.StockMembers.choices, models.StockMembers.get_attribute_types()),
    ('compop', models.OperatorTypes.choices, models.OperatorTypes.get_attribute_types()),
  ], ids=[
    'target',
    'compop',
  ])
  def test_check_widgets(self, get_user, field_name, choices, attrs):
    user = get_user
    form = forms.StockScreenerForm(user=user)
    field = form.fields.get(field_name)
    data_attrs = field.widget.data_attrs

    assert field.choices == choices
    assert data_attrs == attrs

  def test_check_ordering_types(self, get_user):
    user = get_user
    form = forms.StockScreenerForm(user=user)
    ordering_types = form.ordering_types
    exacts = models.StockOrderingTypes.choices

    assert ordering_types == exacts

  @pytest.mark.parametrize([
    'params',
    'is_valid',
  ], [
    ({'title': 'hoge', 'priority':  1, 'condition': 'price < 1000 and code in "5"', 'ordering': '-er'}, True),
    ({'title': 'hoge', 'priority':  1, 'condition': 'price < 1000 and code in "5"', 'ordering': '-er,-code'}, True),
    ({'title':  'foo', 'priority':  0, 'condition': 'price < 1000 and code in "5"'}, True),
    ({'title':  'bar',                 'condition': 'price < 1000 and code in "5"', 'ordering': '-code'}, False),
    ({'title':     '', 'priority':  1, 'condition': 'price < 1000', 'ordering': '-bps'}, False),
    ({                 'priority':  1, 'condition': 'price < 1000', 'ordering': '-roe'}, False),
    ({'title': 'hoge', 'priority':  1, 'condition':             '', 'ordering': 'code'}, False),
    ({'title': 'hoge', 'priority':  1,                              'ordering': 'pbr'}, False),
    ({'title': 'hoge', 'priority':  1, 'condition': 'price < 1000 and hogehoge', 'ordering': 'per'}, False),
    ({'title': 'hoge', 'priority': -1, 'condition': 'price < 1000', 'ordering': '-price'}, False),
    ({'title': 'hoge', 'priority':  1, 'condition': 'price < 1000', 'ordering': 'code-price'}, False),
    ({'title': 'hoge', 'priority':  1, 'condition': 'price < 1000', 'ordering': 'hogehoge'}, False),
  ], ids=[
    'normal-input',
    'normal-input-with-multiple-orderings',
    'ordering-is-not-set',
    'priority-is-not-set',
    'title-is-empty',
    'title-is-not-set',
    'condition-is-empty',
    'condition-is-not-set',
    'has-condition-error',
    'has-priority-error',
    'has-ordering-error',
    'include-invalid-ordering',
  ])
  def test_check_stock_screener_form(self, get_user, params, is_valid):
    user = get_user
    form = forms.StockScreenerForm(user=user, data=params)

    assert form.is_valid() == is_valid