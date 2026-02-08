import pytest
import argparse
from django.core.management import CommandError
from django.contrib.auth import get_user_model
from account import backends
from account.management.commands import custom_createsuperuser

UserModel = get_user_model()

# ======================
# custom_createsuperuser
# ======================
@pytest.mark.account
@pytest.mark.django_db
class TestCustomCreatesuperuserCommand:
  def test_add_arguments(self):
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

  @pytest.mark.parametrize([
    'user_exists',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'same-superuser-exists',
    'register-superuser-for-the-first-time',
  ])
  def test_valid_superuser(self, user_exists):
    options = {
      'username': 'foo',
      'email': 'foo@example.com',
      'password': 'sample'
    }

    if user_exists:
      _ = UserModel.objects.create_superuser(
        username=options['username'],
        email=options['email'],
        password=options['password'],
        screen_name='admin',
        is_staff=True,
        is_superuser=True,
      )
    command = custom_createsuperuser.Command()
    command.handle(**options)
    # Get created user instance
    user = UserModel.objects.get(username=options['username'])

    assert user.email == options['email']
    assert user.check_password(options['password'])
    assert user.screen_name == 'admin'

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
  def test_invalid_args(self, username_exists, email_exists, password_exists):
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
class TestBackends:
  @pytest.mark.parametrize([
    'input_key'
  ], [
    ('username', ),
    ('email', ),
  ], ids=[
    'input-username',
    'input-email',
  ])
  def test_valid_authentication(self, get_user_with_option, input_key):
    option, original = get_user_with_option
    backend = backends.EmailBackend()
    user = backend.authenticate(None, username=option[input_key], password=option['password'])

    assert user is not None
    assert user.username == original.username
    assert user.email == original.email

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
  def test_invalid_authentication(self, get_user_with_option, input_value, is_valid_password, is_active):
    option, original = get_user_with_option
    original.is_active = is_active
    original.save()
    kwargs = {
      'username': input_value,
      'password': option['password'] if is_valid_password else None,
    }
    backend = backends.EmailBackend()
    user = backend.authenticate(None, **kwargs)

    assert user is None

  def test_can_get_user(self, get_user_with_option):
    _, original = get_user_with_option
    backend = backends.EmailBackend()
    user = backend.get_user(user_id=original.pk)

    assert user is not None
    assert user.username == original.username
    assert user.email == original.email

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
  def test_cannot_get_user(self, get_user_with_option, is_valid_pk, is_active):
    _, original = get_user_with_option
    original.is_active = is_active
    original.save()
    user_id = original.pk + (0 if is_valid_pk else 1)
    backend = backends.EmailBackend()
    user = backend.get_user(user_id=user_id)

    assert user is None