from types import FunctionType
from celery import shared_task, states
from celery.utils.log import get_task_logger
from django_celery_results.models import TaskResult
from django.utils.translation import gettext_lazy
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy
from stock.models import Snapshot, convert_timezone
from datetime import datetime, timedelta

UserModel = get_user_model()

try:
  import stock.user_tasks as user_tasks
  _is_function = lambda target: isinstance(target, FunctionType) and (target.__name__ == 'as_udf')
  g_attrs = [attr for attr in dir(user_tasks) if _is_function(getattr(user_tasks, attr))]
except:
  user_tasks = None
  g_attrs = []

# Get logger
g_logger = get_task_logger(__name__)

def _calc_diff_date(offset=1):
  current = timezone.now()
  target = datetime(current.year, current.month, current.day) - timedelta(days=offset-1, seconds=1)
  tz = timezone.get_current_timezone()
  dt_with_current_tz = timezone.make_aware(target, tz)
  shifted_date = dt_with_current_tz.astimezone(timezone.timezone.utc)

  return shifted_date

@shared_task(ignore_result=True)
def delete_successful_tasks():
  queryset = TaskResult.objects.filter(status=states.SUCCESS)

  if queryset.count() > 0:
    try:
      count, _ = queryset.delete()
      g_logger.info(f'The {count} tasks are deleted.')
    except Exception as ex:
      g_logger.error(f'Failed to delete the records that the status of celery task is {states.SUCCESS}({ex}).')

@shared_task(ignore_result=True)
def register_monthly_report(day_offset):
  title_template = gettext_lazy('Monthly report - {date}')
  queryset = UserModel.objects.filter(is_active=True, is_staff=False)
  end_date = _calc_diff_date(day_offset)
  year_month = convert_timezone(end_date, is_string=True, strformat='%Y/%m')
  title = title_template.format(date=year_month)
  records = []

  for user in queryset:
    instance = Snapshot(user=user, title=title, end_date=end_date)
    instance.update_record()
    records += [instance]
  Snapshot.objects.bulk_create(records)

@shared_task(bind=True)
def update_stock_records(self, **kwargs):
  if len(g_attrs) > 0:
    callback = getattr(user_tasks, g_attrs[0])
    ret = callback(logger=g_logger, **kwargs)
  else:
    ret = None

  return ret