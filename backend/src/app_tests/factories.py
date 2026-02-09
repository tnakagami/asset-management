import factory
import uuid
from celery import states
from django.utils import timezone
from django_celery_results.models import TaskResult
from django_celery_beat import models as beat_models
from faker import Factory as FakerFactory
from account.models import User
from stock import models

faker = FakerFactory.create()

def clip(target_name, max_length):
  if len(target_name) > max_length:
    clipped = target_name[:max_length]
  else:
    clipped = target_name

  return clipped

def get_code(idx, max_len=16):
  val = faker.pyint(min_value=0, max_value=9999, step=1)
  alphabets = faker.pystr(min_chars=2, max_chars=5)
  pseudo_code = clip(f'{alphabets}{idx}{val}', max_len)

  return pseudo_code

# =======
# Account
# =======
class UserFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = User

  username = factory.Sequence(lambda idx: f'user{idx}')
  email = factory.LazyAttribute(lambda instance: clip(f'{instance.username}@example.com', 128).lower())
  screen_name = factory.LazyAttribute(lambda instance: clip(faker.name(), 128))
  date_joined = factory.LazyFunction(timezone.now)

# =====
# Stock
# =====
class IndustryFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = models.Industry

  is_defensive = faker.pybool()

class LocalizedIndustryFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = models.LocalizedIndustry

  name = factory.LazyAttribute(lambda instance: clip(faker.name(), 64))
  language_code = 'en'
  industry = factory.SubFactory(IndustryFactory)

class StockFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = models.Stock

  class Params:
    money_params = {
      'right_digits': 2,
      'min_value': 0,
    }
    ratio_params = {
      'left_digits': 5,
      'right_digits': 2,
      'min_value': 0,
    }
    roe_params = {
      'left_digits': 4,
      'right_digits': 2,
      'min_value': 0,
    }
    er_params = {
      'left_digits': 3,
      'right_digits': 2,
      'min_value': 0,
    }

  code = factory.Sequence(lambda idx: get_code(idx, max_len=16))
  industry = factory.SubFactory(IndustryFactory)
  price = factory.LazyAttribute(lambda instance: faker.pydecimal(left_digits=8, **instance.money_params))
  dividend = factory.LazyAttribute(lambda instance: faker.pydecimal(left_digits=5, **instance.money_params))
  per = factory.LazyAttribute(lambda instance: faker.pydecimal(**instance.ratio_params))
  pbr = factory.LazyAttribute(lambda instance: faker.pydecimal(**instance.ratio_params))
  eps = factory.LazyAttribute(lambda instance: faker.pydecimal(**instance.ratio_params))
  bps = factory.LazyAttribute(lambda instance: faker.pydecimal(**instance.ratio_params))
  roe = factory.LazyAttribute(lambda instance: faker.pydecimal(**instance.roe_params))
  er  = factory.LazyAttribute(lambda instance: faker.pydecimal(**instance.er_params))
  skip_task = False

class LocalizedStockFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = models.LocalizedStock

  name = factory.Sequence(lambda idx: f'stock{idx}')
  language_code = 'en'
  stock = factory.SubFactory(StockFactory)

class CashFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = models.Cash

  class Params:
    params = {
      'min_value': 0,
      'max_value': 2**31 - 1,
      'step': 1,
    }

  user = factory.SubFactory(UserFactory)
  balance = factory.LazyAttribute(lambda instance: faker.pyint(**instance.params))
  registered_date = factory.LazyFunction(timezone.now)

class PurchasedStockFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = models.PurchasedStock

  class Params:
    price_params = {
      'left_digits': 9,
      'right_digits': 2,
      'min_value': 0,
    }
    count_params = {
      'min_value': 0,
      'max_value': 1000,
      'step': 1,
    }

  user = factory.SubFactory(UserFactory)
  stock = factory.SubFactory(StockFactory)
  price = factory.LazyAttribute(lambda instance: faker.pydecimal(**instance.price_params))
  purchase_date = factory.LazyFunction(timezone.now)
  count = factory.LazyAttribute(lambda instance: faker.pyint(**instance.count_params))
  has_been_sold = False

class SnapshotFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = models.Snapshot

  user = factory.SubFactory(UserFactory)
  uuid = factory.LazyFunction(uuid.uuid4)
  title = factory.LazyAttribute(lambda instance: clip(faker.name(), 255))
  end_date = factory.LazyFunction(timezone.now)
  created_at = factory.LazyFunction(timezone.now)

class TaskResultFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = TaskResult

  task_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
  task_name = factory.LazyAttribute(lambda instance: f'task{instance.task_id}')
  status = states.PENDING

class CrontabScheduleFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = beat_models.CrontabSchedule

  class Params:
    minute_params = {
      'min_value': 0,
      'max_value': 59,
      'step': 1,
    }
    hour_params = {
      'min_value': 0,
      'max_value': 23,
      'step': 1,
    }
    month_params = {
      'min_value': 1,
      'max_value': 31,
      'step': 1,
    }

  minute = factory.LazyAttribute(lambda obj: str(faker.pyint(**obj.minute_params)))
  hour = factory.LazyAttribute(lambda obj: str(faker.pyint(**obj.hour_params)))
  day_of_month = factory.LazyAttribute(lambda obj: str(faker.pyint(**obj.month_params)))
  month_of_year = '*'
  day_of_week = '*'

class PeriodicTaskFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = beat_models.PeriodicTask

  name = factory.Sequence(lambda idx: clip(f'No.{idx}-task', 200))
  task = 'stock.tasks.update_specific_snapshot'
  crontab = factory.SubFactory(CrontabScheduleFactory)
  enabled = True