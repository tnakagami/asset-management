import pytest
from django.contrib.auth import get_user_model
from dataclasses import dataclass

UserModel = get_user_model()

@pytest.fixture
def get_user_with_option(django_db_blocker):
  option = {
    'username': 'test-sample',
    'email': 'test-sample@example.com',
    'password': 'password1',
  }

  with django_db_blocker.unblock():
    user = UserModel.objects.create_user(**option)

  return option, user