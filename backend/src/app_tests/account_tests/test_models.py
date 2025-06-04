import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError, DataError
from account import models
from . import factories

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_user():
  user = factories.UserFactory.build()

  assert isinstance(user, models.User)

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'username',
  'email',
  'screen_name',
], [
  ('hoge', 'hoge@example.com', 'hogehoge'),
  ('1'*128, '{}@ok.com'.format('1'*121), '1'*128),
  ('foo', 'foo@ok.com', ''),
], ids=[
  'valid',
  'max-length',
  'include-empty-data',
])
def test_user_creation(username, email, screen_name):
  user = factories.UserFactory(username=username, email=email, screen_name=screen_name)

  assert user.username == username
  assert user.email == email
  assert user.screen_name == screen_name

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_superuser_creation():
  _user = factories.UserFactory.build()
  superuser = models.User.objects.create_superuser(
    username=_user.username,
    email=_user.email,
    is_staff=True,
    is_superuser=True,
  )
  assert superuser.is_staff
  assert superuser.is_superuser

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_superuser_is_not_staffuser():
  _user = factories.UserFactory.build()
  err = 'Superuser must have is_staff=True.'

  with pytest.raises(ValueError) as ex:
    superuser = models.User.objects.create_superuser(
      username=_user.username,
      email=_user.email,
      is_staff=False,
      is_superuser=True,
    )
  assert err in ex.value.args

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_superuser_is_not_superuser():
  _user = factories.UserFactory.build()
  err = 'Superuser must have is_superuser=True.'

  with pytest.raises(ValueError) as ex:
    superuser = models.User.objects.create_superuser(
      username=_user.username,
      email=_user.email,
      is_staff=True,
      is_superuser=False,
    )
  assert err in ex.value.args

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_empty_username():
  _user = factories.UserFactory.build()
  err = 'The given username must be set'

  with pytest.raises(ValueError) as ex:
    models.User.objects.create_user(username='', email=_user.email)
  assert err in ex.value.args

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_empty_email():
  _user = factories.UserFactory.build()
  err = 'The given email must be set'

  with pytest.raises(ValueError) as ex:
    models.User.objects.create_user(username=_user.username, email='')
  assert err in ex.value.args

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_invalid_username():
  with pytest.raises(DataError):
    user = factories.UserFactory.build(username='1'*129)
    user.save()

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_invalid_screen_name():
  with pytest.raises(DataError):
    user = factories.UserFactory.build(screen_name='1'*129)
    user.save()

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_invalid_same_username():
  username = 'hoge'
  valid_user = factories.UserFactory.build(username=username)
  valid_user.save()

  with pytest.raises(IntegrityError):
    invalid_user = factories.UserFactory.build(username=username)
    invalid_user.save()

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_invalid_same_email():
  email = 'hoge@example.com'
  valid_user = factories.UserFactory.build(email=email)
  valid_user.save()

  with pytest.raises(IntegrityError):
    invalid_user = factories.UserFactory.build(email=email)
    invalid_user.save()

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'username',
  'screen_name',
  'expected'
], [
  ('1'*32, '2'*32, '2'*32,), 
  ('1'*32, '', '1'*32,),
  ('1'*32, '2'*33, '{}...'.format('2'*32)), 
  ('1'*33, '', '{}...'.format('1'*32)), 
], ids=[
  'length-eq-32',
  'screen-name-is-empty',
  'screen-name-length-is-33',
  'username-length-is-33',
])
def test_user_shortname(username, screen_name, expected):
  user = factories.UserFactory(username=username, screen_name=screen_name)

  assert user.get_short_name() == expected

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'username',
  'screen_name',
  'expected',
], [
  ('1'*32, '2'*32, '2'*32,), 
  ('1'*32, '', '1'*32,),
  ('1'*33, '2'*33, '2'*33), 
  ('1'*33, '', '1'*33),
  ('1'*128, '2'*128, '2'*128),
  ('1'*128, '', '1'*128),
], ids=[
  'length-eq-32',
  'usename-length-eq-32-screen-name-is-empty',
  'length-eq-33',
  'username-length-eq-33-screen-name-is-empty',
  'length-eq-128',
  'username-length-eq-128-screen-name-is-empty',
])
def test_user_fullname(username, screen_name, expected):
  user = factories.UserFactory(username=username, screen_name=screen_name)

  assert user.get_full_name() == expected