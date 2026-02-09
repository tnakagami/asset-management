import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError, DataError
from account import models
from app_tests import factories

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
class TestUser:
  def test_user_instance_type(self):
    user = factories.UserFactory.build()

    assert isinstance(user, models.User)

  @pytest.mark.parametrize([
    'username',
    'email',
    'kwargs',
  ], [
    ('hoge', 'hoge@example.com', {'screen_name': 'hogehoge'}),
    ('1'*128, '{}@ok.com'.format('1'*121), {'screen_name': '1'*128}),
    ('foo', 'foo@ok.com', {'screen_name': ''}),
    ('foo', 'foo@ok.com', {}),
  ], ids=[
    'valid-data',
    'max-length',
    'include-blank-data',
    'include-empty-data',
  ])
  def test_user_creation(self, username, email, kwargs):
    user = models.User.objects.create_user(
      username=username,
      email=email,
      **kwargs,
    )

    assert user.username == username
    assert user.email == email
    assert user.screen_name == kwargs.get('screen_name', '')

  def test_superuser_creation(self):
    base_user = factories.UserFactory.build()
    superuser = models.User.objects.create_superuser(
      username=base_user.username,
      email=base_user.email,
      is_staff=True,
      is_superuser=True,
    )
    assert superuser.is_staff
    assert superuser.is_superuser

  def test_superuser_is_not_staffuser(self):
    base_user = factories.UserFactory.build()
    err = 'Superuser must have is_staff=True.'

    with pytest.raises(ValueError) as ex:
      superuser = models.User.objects.create_superuser(
        username=base_user.username,
        email=base_user.email,
        is_staff=False,
        is_superuser=True,
      )
    assert err in ex.value.args

  def test_superuser_is_not_superuser(self):
    base_user = factories.UserFactory.build()
    err = 'Superuser must have is_superuser=True.'

    with pytest.raises(ValueError) as ex:
      superuser = models.User.objects.create_superuser(
        username=base_user.username,
        email=base_user.email,
        is_staff=True,
        is_superuser=False,
      )
    assert err in ex.value.args

  def test_empty_username(self):
    base_user = factories.UserFactory.build()
    err = 'The given username must be set'

    with pytest.raises(ValueError) as ex:
      models.User.objects.create_user(
        username='',
        email=base_user.email,
      )
    assert err in ex.value.args

  def test_empty_email(self):
    base_user = factories.UserFactory.build()
    err = 'The given email must be set'

    with pytest.raises(ValueError) as ex:
      models.User.objects.create_user(
        username=base_user.username,
        email='',
      )
    assert err in ex.value.args

  def test_invalid_username(self):
    with pytest.raises(DataError):
      base_user = factories.UserFactory.build()
      models.User.objects.create_user(
        username='1'*129,
        email=base_user.email,
      )

  def test_invalid_screen_name(self):
    with pytest.raises(DataError):
      base_user = factories.UserFactory.build()
      models.User.objects.create_user(
        username=base_user.username,
        email=base_user.email,
        screen_name='1'*129,
      )

  def test_invalid_same_username(self):
    base_user = factories.UserFactory()

    with pytest.raises(IntegrityError):
      models.User.objects.create_user(
        username=base_user.username,
        email=f'mail{base_user.pk}@example.com',
      )

  def test_invalid_same_email(self):
    base_user = factories.UserFactory()

    with pytest.raises(IntegrityError):
      models.User.objects.create_user(
        username=f'hoge{base_user.pk}',
        email=base_user.email,
      )

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
  def test_check_shortname(self, username, screen_name, expected):
    user = factories.UserFactory(
      username=username,
      screen_name=screen_name,
    )

    assert user.get_short_name() == expected

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
  def test_check_fullname(self, username, screen_name, expected):
    user = factories.UserFactory(
      username=username,
      screen_name=screen_name,
    )

    assert user.get_full_name() == expected