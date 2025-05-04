import pytest

@pytest.fixture(scope='session', autouse=True)
def django_db_setup(django_db_setup):
  pass

@pytest.fixture(autouse=True)
def setup_django(settings):
  settings.LANGUAGE_CODE = 'en'

@pytest.fixture
def csrf_exempt_django_app(django_app_factory):
  app = django_app_factory(csrf_checks=False)

  return app