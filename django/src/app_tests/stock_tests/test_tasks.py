import pytest
from celery import states
from django_celery_results.models import TaskResult
from . import factories

class FakeUserTask:
  def __init__(self):
    self.logger = None
    self.kwargs = {}

  def my_task(self, **kwargs):
    self.logger = kwargs.pop('logger')
    self.kwargs = kwargs

    return 0

@pytest.mark.stock
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

  class FakeLogger:
    def __init__(self):
      self.msg = ''
    def store(self, msg):
      self.msg = msg

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