import factory
from django.utils import timezone
from faker import Factory as FakerFactory
from account import models

faker = FakerFactory.create()

def clip(target_name, max_length):
  if len(target_name) > max_length:
    clipped = target_name[:max_length]
  else:
    clipped = target_name

  return clipped

class UserFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = models.User

  username = factory.Sequence(lambda idx: f'user{idx}')
  email = factory.LazyAttribute(lambda instance: clip(f'{instance.username}@example.com', 128).lower())
  screen_name = factory.LazyAttribute(lambda instance: clip(faker.name(), 128))
  date_joined = factory.LazyFunction(timezone.now)