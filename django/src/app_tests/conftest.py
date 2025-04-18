import pytest

@pytest.fixture(scope='session', autouse=True)
def django_db_setup(django_db_setup):
  pass

@pytest.fixture(autouse=True)
def setup_django(settings):
  settings.LANGUAGE_CODE = 'en'