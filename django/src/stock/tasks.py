from types import FunctionType
from celery import shared_task, states
from celery.utils.log import get_task_logger
from django_celery_results.models import TaskResult

try:
  import stock.user_tasks as user_tasks
  _is_function = lambda target: isinstance(target, FunctionType) and (target.__name__ == 'as_udf')
  g_attrs = [attr for attr in dir(user_tasks) if _is_function(getattr(user_tasks, attr))]
except:
  user_tasks = None
  g_attrs = []

# Get logger
g_logger = get_task_logger(__name__)

@shared_task(ignore_result=True)
def delete_successful_tasks():
  queryset = TaskResult.objects.filter(status=states.SUCCESS)

  if queryset.count() > 0:
    try:
      count, _ = queryset.delete()
      g_logger.info(f'The {count} tasks are deleted.')
    except Exception as ex:
      g_logger.error(f'Failed to delete the records that the status of celery task is {states.SUCCESS}({ex}).')

@shared_task(bind=True)
def update_stock_records(self, **kwargs):
  if len(g_attrs) > 0:
    callback = getattr(user_tasks, g_attrs[0])
    ret = callback(logger=g_logger, **kwargs)
  else:
    ret = None

  return ret