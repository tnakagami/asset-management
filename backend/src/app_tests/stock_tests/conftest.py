import pytest
from app_tests import factories

@pytest.fixture(scope='module')
def get_user(django_db_blocker):
  with django_db_blocker.unblock():
    user = factories.UserFactory()

  return user