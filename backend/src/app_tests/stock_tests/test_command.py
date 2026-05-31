import pytest
import io
from django.core.management import call_command
from django.core.management.base import CommandError
from stock import models
from stock.management.commands import run_stock_task
from app_tests import factories, BaseTestUtils

class DummyStock:
  def __init__(self, pk, code):
    self.pk = pk
    self.code = code

@pytest.mark.stock
@pytest.mark.django_db
class TestInitProcess(BaseTestUtils):
  @pytest.mark.parametrize([
    'pk',
    'code',
  ], [
    (2, '1234'),
    (3, '5678'),
    (4, '90ab'),
    (5, 'xyzw'),
    (6, 'stuv'),
    (7, '50A1'),
  ], ids=lambda val: f'pk{val}' if isinstance(val, int) else str(val))
  def test_run_stock_task(self, mocker, pk, code):
    instance = DummyStock(pk, code)
    func_mock = mocker.patch('stock.management.commands.update_stock_records.apply_async', return_value=None)
    run_stock_task(10, 123, instance)
    _, actual_kwargs = func_mock.call_args
    kwargs = actual_kwargs['kwargs']

    assert func_mock.call_count == 1
    assert kwargs.get('idx') == 10
    assert kwargs.get('pk') == pk
    assert kwargs.get('code') == code
    assert kwargs.get('total') == 123

@pytest.mark.stock
@pytest.mark.django_db
class TestExecJob(BaseTestUtils):
  @pytest.fixture(scope='class')
  def get_dummy_stock_data(self, django_db_blocker):
    with django_db_blocker.unblock():
      industry = factories.IndustryFactory()
      stocks = factories.StockFactory.create_batch(202, industry=industry)

    return stocks

  @pytest.mark.parametrize([
    'num',
    'count',
  ], [
    (99,  0),
    (100, 1),
    (101, 1),
    (199, 1),
    (200, 2),
    (201, 2),
  ], ids=lambda val: f'v{val}')
  def test_call_background_job(self, mocker, get_dummy_stock_data, num, count):
    stocks = get_dummy_stock_data
    queryset = models.Stock.objects.filter(pk__in=self.get_pks(stocks[:num]))
    # Setup mock
    mocker.patch('stock.models.Stock.objects.select_targets', return_value=queryset)
    func_mock = mocker.patch('stock.management.commands.exec_job.run_stock_task', return_value=None)
    out_mock = mocker.MagicMock()
    call_command('exec_job', stdout=out_mock)

    assert func_mock.call_count == num
    assert out_mock.write.call_count == count + 1

@pytest.mark.stock
@pytest.mark.django_db
class TestManualUpdate(BaseTestUtils):
  @pytest.fixture(scope='class')
  def get_dummy_stock_data(self, django_db_blocker):
    with django_db_blocker.unblock():
      industries = [
        factories.IndustryFactory(),
        factories.IndustryFactory()
      ]
      stocks = [
        factories.StockFactory(code='test0x1234', industry=industries[0]),
        factories.StockFactory(code='test0x3564', industry=industries[1]),
        factories.StockFactory(code='test0x7714', industry=industries[0]),
        factories.StockFactory(code='test0x8691', industry=industries[1]),
      ]

    return stocks

  @pytest.fixture
  def run_process(self, mocker, get_dummy_stock_data):
    def inner(*args):
      instances = get_dummy_stock_data
      queryset = models.Stock.objects.filter(pk__in=self.get_pks(instances))
      mocker.patch('stock.models.Stock.objects.select_targets', return_value=queryset)
      func_mock = mocker.patch('stock.management.commands.manual_update.run_stock_task', return_value=None)
      out = io.StringIO()
      call_command('manual_update', '--stock-codes', *args, stdout=out)
      output = out.getvalue()

      return output, func_mock

    return inner

  def test_valid_codes(self, run_process):
    output, func_mock = run_process('test0x1234', 'test0x8691')

    assert func_mock.call_count == 2
    assert 'All jobs have been started(total: 2).' in output
    assert 'Error' not in output

  def test_valid_codes_with_whitespace(self, run_process):
    output, func_mock = run_process('test0x1234  ', 'test0x8691')

    assert func_mock.call_count == 2
    assert 'All jobs have been started(total: 2).' in output
    assert 'Error' not in output

  def test_skip_invalid_code(self, run_process):
    output, func_mock = run_process('test0x1234', 'invalid')

    assert func_mock.call_count == 1
    assert 'All jobs have been started(total: 1).' in output
    assert 'Error' not in output

  def test_no_valid_codes_exist(self, run_process):
    output, func_mock = run_process('missing', 'invalid')

    assert func_mock.call_count == 0
    assert 'Error: No valid code has been specified.' in output
    assert 'All jobs have been started' not in output

  def test_command_error_when_required_argument_missing(self):
    with pytest.raises(CommandError):
      call_command('manual_update')

  def test_only_empty_spaces(self, run_process):
    output, func_mock = run_process('   ', ' ')

    assert func_mock.call_count == 0
    assert 'Error: No valid code has been specified.' in output
    assert 'All jobs have been started' not in output