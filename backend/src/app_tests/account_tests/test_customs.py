import pytest
import argparse
from django.core.management import CommandError
from django.contrib.auth import get_user_model
from account import backends
from account.management.commands import custom_createsuperuser
from dataclasses import dataclass

User = get_user_model()

@dataclass
class _UserInfo:
  password: str
  exact_user: User

@pytest.fixture
def init_record(django_db_blocker):
  password = 'abc123'
  options = {
    'username': 'foo',
    'email': 'hoge@example.com',
    'password': password,
  }

  with django_db_blocker.unblock():
    info = _UserInfo(password=password, exact_user=User.objects.create_user(**options))

  return info

# ======================
# custom_createsuperuser
# ======================
@pytest.mark.account
def test_add_arguments():
  username = 'hoge'
  email = 'foo@example.com'
  password = 'abc123'
  inputs = ['--username', username, '--email', email, '--password', password]
  command = custom_createsuperuser.Command()
  parser = argparse.ArgumentParser()
  command.add_arguments(parser)
  args = parser.parse_args(inputs)
  assert args.username == username
  assert args.email == email
  assert args.password == password

@pytest.mark.account
@pytest.mark.django_db
@pytest.mark.parametrize([
  'user_exists',
], [
  (True, ),
  (False, ),
], ids=[
  'same-superuser-exists',
  'register-superuser-for-the-first-time',
])
def test_valid_superuser(user_exists):
  options = {
    'username': 'foo',
    'email': 'foo@example.com',
    'password': 'sample'
  }

  if user_exists:
    _ = User.objects.create_superuser(**options, screen_name='admin')
  command = custom_createsuperuser.Command()
  command.handle(**options)

  user = User.objects.get(username=options['username'])
  assert user.email == options['email']
  assert user.check_password(options['password'])
  assert user.screen_name == 'admin'

@pytest.mark.account
@pytest.mark.parametrize([
  'username_exists',
  'email_exists',
  'password_exists',
], [
  (False, False, False),
  (False, False, True),
  (False, True,  False),
  (False, True,  True),
  (True,  False, False),
  (True,  False, True),
  (True,  True,  False),
], ids=[
  'all-items-are-empty',
  'only-password',
  'only-email',
  'username-is-empty',
  'only-username',
  'email-is-empty',
  'password-is-empty',
])
def test_invalid_args(username_exists, email_exists, password_exists):
  pairs = {
    'username': (username_exists, 'foo'),
    'email':    (email_exists, 'hoge@example.com'),
    'password': (password_exists, 'abc123'),
  }
  options = {key: val for key, (flag, val) in pairs.items() if flag}
  err = '--username, --email and --password are required options'
  command = custom_createsuperuser.Command()

  with pytest.raises(CommandError) as ex:
    command.handle(**options)
  assert err == str(ex.value)

# ========
# backends
# ========
@pytest.mark.account
@pytest.mark.django_db
@pytest.mark.parametrize([
  'input_value'
], [
  ('foo', ),
  ('hoge@example.com', ),
], ids=[
  'input-username',
  'input-password',
])
def test_valid_authentication(init_record, input_value):
  info = init_record
  backend = backends.EmailBackend()
  user = backend.authenticate(None, username=input_value, password=info.password)

  assert user is not None
  assert user.username == info.exact_user.username
  assert user.email == info.exact_user.email

@pytest.mark.account
@pytest.mark.django_db
@pytest.mark.parametrize([
  'input_value',
  'is_valid_password',
  'is_active',
], [
  ('invalid-username', True, True),
  ('invalid-email', True, True),
  ('foo', False, True),
  ('foo', True, False),
], ids=[
  'invalid-username',
  'invalid-email',
  'invalid-password',
  'user-is-not-active',
])
def test_invalid_authentication(init_record, input_value, is_valid_password, is_active):
  info = init_record
  info.exact_user.is_active = is_active
  info.exact_user.save()
  kwargs = {
    'username': input_value,
    'password': info.password if is_valid_password else None,
  }
  backend = backends.EmailBackend()
  user = backend.authenticate(None, **kwargs)

  assert user is None

@pytest.mark.account
@pytest.mark.django_db
def test_can_get_user(init_record):
  info = init_record
  backend = backends.EmailBackend()
  user = backend.get_user(user_id=info.exact_user.pk)

  assert user is not None
  assert user.username == info.exact_user.username
  assert user.email == info.exact_user.email

@pytest.mark.account
@pytest.mark.django_db
@pytest.mark.parametrize([
  'is_valid_pk',
  'is_active',
], [
  (False, True),
  (True, False),
], ids=[
  'invalid-pk',
  'user-is-not-active',
])
def test_cannot_get_user(init_record, is_valid_pk, is_active):
  info = init_record
  info.exact_user.is_active = is_active
  info.exact_user.save()
  user_id = info.exact_user.pk + (0 if is_valid_pk else 1)
  backend = backends.EmailBackend()
  user = backend.get_user(user_id=user_id)

  assert user is None