import factory
import uuid
from django.utils import timezone
from faker import Factory as FakerFactory
from stock import models
from django_celery_results.models import TaskResult
from celery import states
from app_tests.account_tests import factories as account_factories

faker = FakerFactory.create()
_clip = account_factories.clip
UserFactory = account_factories.UserFactory

def _get_code(max_len):
  val = faker.pyint(min_value=0, max_value=9999, step=1)
  alphabets = faker.pystr(min_chars=2, max_chars=5)
  pseudo_code = _clip(f'{alphabets}{val}', max_len)

  return pseudo_code

class IndustryFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = models.Industry

  name = factory.LazyAttribute(lambda instance: _clip(faker.name(), 64))
  is_defensive = faker.pybool()

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

  code = factory.LazyAttribute(lambda instance: _get_code(16))
  name = factory.LazyAttribute(lambda instance: _clip(faker.name(), 255))
  industry = factory.SubFactory(IndustryFactory)
  price = factory.LazyAttribute(lambda instance: faker.pydecimal(left_digits=8, **instance.money_params))
  dividend = factory.LazyAttribute(lambda instance: faker.pydecimal(left_digits=5, **instance.money_params))
  per = factory.LazyAttribute(lambda instance: faker.pydecimal(**instance.ratio_params))
  pbr = factory.LazyAttribute(lambda instance: faker.pydecimal(**instance.ratio_params))
  eps = factory.LazyAttribute(lambda instance: faker.pydecimal(**instance.ratio_params))

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

class SnapshotFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = models.Snapshot

  user = factory.SubFactory(UserFactory)
  uuid = factory.LazyFunction(uuid.uuid4)
  title = factory.LazyAttribute(lambda instance: _clip(faker.name(), 255))
  end_date = factory.LazyFunction(timezone.now)
  created_at = factory.LazyFunction(timezone.now)

class TaskResultFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = TaskResult

  task_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
  task_name = factory.LazyAttribute(lambda instance: f'task{instance.task_id}')
  status = states.PENDING