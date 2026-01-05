import pytest
import json
from celery import states
from datetime import datetime, timezone
from decimal import Decimal
from django_celery_results.models import TaskResult
from django.contrib.auth import get_user_model
from zoneinfo import ZoneInfo
from stock.models import convert_timezone, Snapshot
from . import factories

UserModel = get_user_model()

class FakeUserTask:
  def __init__(self):
    self.logger = None
    self.kwargs = {}

  def my_task(self, **kwargs):
    self.logger = kwargs.pop('logger')
    self.kwargs = kwargs

    return 0

class FakeLogger:
  def __init__(self):
    self.msg = ''
  def store(self, msg):
    self.msg = msg

@pytest.mark.stock
@pytest.mark.task
@pytest.mark.parametrize([
  'current_date',
  'offset',
  'expected_date'
], [
  (datetime(2000,1,2, 9,0,0, tzinfo=ZoneInfo('Asia/Tokyo')),       3, datetime(1999,12,30,14,59,59, tzinfo=timezone.utc)), # UTC+9
  (datetime(2000,1,2,10,0,0, tzinfo=ZoneInfo('Asia/Tokyo')),       2, datetime(1999,12,31,14,59,59, tzinfo=timezone.utc)), # UTC+9
  (datetime(2000,1,2,11,0,0, tzinfo=ZoneInfo('Asia/Tokyo')),       1, datetime(2000, 1, 1,14,59,59, tzinfo=timezone.utc)), # UTC+9
  (datetime(2000,4,1,12,0,0, tzinfo=ZoneInfo('Asia/Tokyo')),       2, datetime(2000, 3,30,14,59,59, tzinfo=timezone.utc)), # UTC+9
  (datetime(2000,4,1,13,0,0, tzinfo=ZoneInfo('Asia/Tokyo')),       1, datetime(2000, 3,31,14,59,59, tzinfo=timezone.utc)), # UTC+9
  (datetime(2000,1,1, 8,0,0, tzinfo=ZoneInfo('America/New_York')), 1, datetime(2000, 1, 1, 4,59,59, tzinfo=timezone.utc)), # UTC-5
  (datetime(2000,1,1,18,0,0, tzinfo=ZoneInfo('Asia/Karachi')),     1, datetime(1999,12,31,18,59,59, tzinfo=timezone.utc)), # UTC+5
], ids=[
  'offset-3-20000102',
  'offset-2-20000102',
  'offset-1-20000102',
  'offset-2-20000401',
  'offset-1-20000401',
  'offset-1-20000101-NY',
  'offset-1-20000101-India',
])
def test_check_calc_diff_date(mocker, current_date, offset, expected_date):
  import stock.tasks
  mocker.patch.object(stock.tasks.timezone, 'now', return_value=current_date)
  mocker.patch.object(stock.tasks.timezone, 'get_current_timezone', return_value=current_date.tzinfo)
  estimated_date = stock.tasks._calc_diff_date(offset)

  assert estimated_date.year == expected_date.year
  assert estimated_date.month == expected_date.month
  assert estimated_date.day == expected_date.day
  assert estimated_date.hour == expected_date.hour
  assert estimated_date.minute == expected_date.minute
  assert estimated_date.second == expected_date.second

@pytest.mark.stock
@pytest.mark.task
@pytest.mark.django_db
@pytest.mark.parametrize([
  'num_tasks',
  'is_raise',
  'expected',
  'log_message',
], [
  (0, True, 1, ''),
  (1, False, 1, 'The 1 tasks are deleted.'),
  (2, False, 1, 'The 2 tasks are deleted.'),
  (1, True, 2, 'Failed to delete the records'),
], ids=[
  'no-tasks-exist',
  'can-delete-one-task-record',
  'can-delete-two-task-records',
  'failed-to-delete-task',
])
def test_check_delete_task_records(mocker, num_tasks, is_raise, expected, log_message):
  import stock.tasks
  _ = factories.TaskResultFactory.create_batch(num_tasks, status=states.SUCCESS)
  _ = factories.TaskResultFactory(status=states.PENDING)
  fake_logger = FakeLogger()
  mocker.patch.object(stock.tasks.g_logger, 'info', side_effect=lambda msg: fake_logger.store(msg))
  mocker.patch.object(stock.tasks.g_logger, 'error', side_effect=lambda msg: fake_logger.store(msg))

  if is_raise:
    mocker.patch('django.db.models.query.QuerySet.delete', side_effect=Exception())
  # Call target method
  stock.tasks.delete_successful_tasks()
  # Check total records of TaskResult model
  total = TaskResult.objects.all().count()

  assert log_message in fake_logger.msg
  assert total == expected

@pytest.mark.stock
@pytest.mark.task
@pytest.mark.django_db
@pytest.mark.parametrize([
  'attrs',
  'checker',
  'expected_kwargs',
], [
  ([], lambda ret: ret is None, {}),
  (['my_task'], lambda ret: ret == 0, {'param': '1', 'data': 2}),
  (['my_task', 'dummy'], lambda ret: ret == 0, {'param': '1', 'data': 2}),
], ids=[
  'user-task-is-empty',
  'define-only-one-function',
  'define-more-than-two-functions',
])
def test_check_update_stock_records(mocker, attrs, checker, expected_kwargs):
  import stock.tasks
  _user_task = FakeUserTask()
  mocker.patch.object(stock.tasks, 'user_tasks', _user_task)
  mocker.patch.object(stock.tasks, 'g_attrs', attrs)
  # Call target function
  ret = stock.tasks.update_stock_records(param='1', data=2)

  assert checker(ret)
  assert all([expected_kwargs[key] == val for key, val in _user_task.kwargs.items()])

@pytest.mark.stock
@pytest.mark.task
def test_raise_import_exception(mocker):
  import sys
  import importlib
  original_function = importlib._bootstrap._find_and_load

  def _fake_finder(name, *args, **kwargs):
    # Raise Exception when specific filepath is given
    if name == 'stock.user_tasks':
      raise Exception()

    return original_function(name, *args, **kwargs)

  # Reset cached module data
  _fake_modules = {key: val for key, val in sys.modules.items() if key not in ['stock.user_tasks', 'stock.tasks']}
  mocker.patch.dict('sys.modules', _fake_modules, clear=True)
  # Mock find_spec method
  mocker.patch('importlib._bootstrap._find_and_load', side_effect=_fake_finder)

  # main routine
  import stock.tasks

  assert stock.tasks.user_tasks is None
  assert len(stock.tasks.g_attrs) == 0

# ====================
# Check monthly report
# ====================
@pytest.fixture
def pseudo_stock_data(django_db_blocker):
  with django_db_blocker.unblock():
    industries = [
      factories.IndustryFactory(),
      factories.IndustryFactory(),
    ]
    localized_industries = [
      factories.LocalizedIndustryFactory(industry=industries[0], name='hoge-company'),
      factories.LocalizedIndustryFactory(industry=industries[1], name='foobar-hd'),
    ]
    stock_params = [
      {'code': '1234', 'name': 'X-company', 'industry': 0, 'price': '1105', 'dividend': '20',
        'per':  '0.21', 'pbr': '2.01', 'eps': '2.5', 'bps': '2.7', 'roe': '5.2', 'er': '43.2'},
      {'code': '5678', 'name': 'Y-company', 'industry': 1, 'price': '2401', 'dividend': '35',
        'per':  '0.32', 'pbr': '3.12', 'eps': '0.7', 'bps': '1.4', 'roe': '5.9', 'er': '21.7'},
      {'code': 'ABCD', 'name': 'Z-company', 'industry': 1, 'price': '1507', 'dividend': '45',
        'per':  '1.32', 'pbr': '5.12', 'eps': '1.7', 'bps': '7.4', 'roe': '3.1', 'er': '50.7'},
    ]
    stocks = [
      factories.StockFactory(
        code=kwargs['code'], industry=industries[kwargs['industry']],
        price=Decimal(kwargs['price']), dividend=Decimal(kwargs['dividend']),
        per=Decimal(kwargs['per']), pbr=Decimal(kwargs['pbr']), eps=Decimal(kwargs['eps']),
        bps=Decimal(kwargs['bps']), roe=Decimal(kwargs['roe']), er=Decimal(kwargs['er']), skip_task=False,
      ) for kwargs in stock_params
    ]
    localized_stocks = [
      factories.LocalizedStockFactory(stock=stock, name=kwargs['name'])
      for stock, kwargs in zip(stocks, stock_params)
    ]

  return stocks

@pytest.fixture(params=['only-one-user', 'multi-users'])
def get_pseudo_pstock_records(django_db_blocker, pseudo_stock_data, request):
  with django_db_blocker.unblock():
    foo = factories.UserFactory(username='monthly-foo', screen_name='monthly foo')
    stocks = pseudo_stock_data
    kwargs = {
      'user': foo,
      'price': Decimal('1230'),
      'count': 100,
    }
    pstocks = [
      factories.PurchasedStockFactory(stock=stocks[0], purchase_date=datetime(2000,1,30,1,2,3, tzinfo=timezone.utc), **kwargs),
      factories.PurchasedStockFactory(stock=stocks[1], purchase_date=datetime(2000,1,31,1,2,3, tzinfo=timezone.utc), **kwargs),
      factories.PurchasedStockFactory(stock=stocks[1], purchase_date=datetime(2000,2, 1,1,2,3, tzinfo=timezone.utc), **kwargs),
    ]
    users = [foo]
    pattern = 'single'
    # Check execution pattern
    if request.param == 'multi-users':
      bar = factories.UserFactory(username='monthly-bar', screen_name='monthly bar')
      kwargs = {
        'user': bar,
        'price': Decimal('1231'),
        'count': 200,
      }
      pstocks += [
        factories.PurchasedStockFactory(stock=stocks[1], purchase_date=datetime(2000,1,30,1,2,3, tzinfo=timezone.utc), **kwargs),
        factories.PurchasedStockFactory(stock=stocks[0], purchase_date=datetime(2000,1,31,1,2,3, tzinfo=timezone.utc), **kwargs),
        factories.PurchasedStockFactory(stock=stocks[2], purchase_date=datetime(2000,2, 1,1,2,3, tzinfo=timezone.utc), **kwargs),
      ]
      users += [bar]
      pattern = 'multi'

  return pattern, users, pstocks

@pytest.mark.stock
@pytest.mark.task
@pytest.mark.django_db
@pytest.mark.parametrize([
  'offset',
  'expected_pstock_ids',
], [
  (0, {'single': [0, 1, 2], 'multi': [3, 4, 5]}),
  (1, {'single': [0, 1, 2], 'multi': [3, 4, 5]}),
  (2, {'single': [0, 1], 'multi': [3, 4]}),
  (3, {'single': [0], 'multi': [3]}),
], ids=[
  'offset-0',
  'offset-1',
  'offset-2',
  'offset-3',
])
def test_register_monthly_report(mocker, get_pseudo_pstock_records, offset, expected_pstock_ids):
  def _check_extracted_pstocks(snapshot, pstocks, indices):
    data = json.loads(snapshot.detail)
    dates = [convert_timezone(pstocks[idx].purchase_date, is_string=True) for idx in indices]
    ret = all([
      len(data['cash']) == 0,
      len(data['purchased_stocks']) == len(indices),
      all([record['purchase_date'] in dates for record in data['purchased_stocks']]),
    ])

    return ret

  import stock.tasks
  pattern, users, pstocks = get_pseudo_pstock_records
  mock_diff_date = mocker.patch.object(stock.tasks.timezone, 'now', return_value=datetime(2000,2,2,1,2,3, tzinfo=timezone.utc))
  # Call target function
  try:
    stock.tasks.register_monthly_report(offset)
  except Exception as ex:
    pytest.fail(f'Unexpected Error: {ex}')

  assert mock_diff_date.call_count == 1
  assert all([user.snapshots.all().count() == 1 for user in users])
  assert all([_check_extracted_pstocks(user.snapshots.all().first(), pstocks, expected_pstock_ids[pattern]) for user in users])

# ================================
# Check updating specific snapshot
# ================================
@pytest.mark.stock
@pytest.mark.task
@pytest.mark.django_db
@pytest.mark.parametrize([
  'is_raise',
  'log_message',
], [
  (False, ''),
  (True, 'Failed to update the record'),
], ids=[
  'valid-inputs',
  'invalid-inputs',
])
def test_check_update_specific_snapshot(mocker, get_pseudo_pstock_records, is_raise, log_message):
  import stock.tasks
  fake_logger = FakeLogger()
  mocker.patch.object(stock.tasks.g_logger, 'error', side_effect=lambda msg: fake_logger.store(msg))
  pattern, users, pstocks = get_pseudo_pstock_records
  table = {'single': [0, 1, 2], 'multi': [3, 4, 5]}
  indices = table[pattern]

  for _user in users:
    ss = factories.SnapshotFactory(user=_user, end_date=datetime(2000,1,31,9,3,0, tzinfo=timezone.utc))
  ss.end_date = datetime(2000,2,2,1,2,3, tzinfo=timezone.utc)
  ss.save()

  if is_raise:
    mocker.patch('stock.models.Snapshot.update_record', side_effect=Exception('Err'))
    detail = json.loads(ss.detail)
    expected_len = len(detail['purchased_stocks'])
    dates = [record['purchase_date'] for record in detail['purchased_stocks']]
  else:
    expected_len = len(indices)
    dates = [convert_timezone(pstocks[idx].purchase_date, is_string=True) for idx in indices]
  # Call target method
  stock.tasks.update_specific_snapshot(user_pk=users[-1].pk, snapshot_pk=ss.pk)
  instance = Snapshot.objects.get(pk=ss.pk)
  data = json.loads(instance.detail)

  assert log_message in fake_logger.msg
  assert len(data['purchased_stocks']) == expected_len
  assert all([record['purchase_date'] in dates for record in data['purchased_stocks']])