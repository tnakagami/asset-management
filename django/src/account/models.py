from django.db import models
from django.contrib.auth.models import PermissionsMixin, UserManager
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy

class CustomUserManager(UserManager):
  use_in_migrations = True

  def _create_user(self, username, email, password, **extra_fields):
    if not username:
        raise ValueError('The given username must be set')
    if not email:
        raise ValueError('The given email must be set')
    username = self.model.normalize_username(username)
    email = self.normalize_email(email)
    user = self.model(username=username, email=email, **extra_fields)
    user.set_password(password)
    user.save(using=self._db)

    return user

  def create_user(self, username, email, password=None, **extra_fields):
    extra_fields.setdefault('is_staff', False)
    extra_fields.setdefault('is_superuser', False)

    return self._create_user(username, email, password,  **extra_fields)

  def create_superuser(self, username, email, password=None, **extra_fields):
    extra_fields.setdefault('is_staff', True)
    extra_fields.setdefault('is_superuser', True)

    if extra_fields.get('is_staff') is not True:
        raise ValueError('Superuser must have is_staff=True.')
    if extra_fields.get('is_superuser') is not True:
        raise ValueError('Superuser must have is_superuser=True.')

    return self._create_user(username, email, password,  **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
  username_validator = UnicodeUsernameValidator()

  username = models.CharField(
    gettext_lazy('username'),
    max_length=128,
    unique=True,
    help_text=gettext_lazy('Required. 128 characters allowing only Unicode characters, in addition to @, ., +, -, and _.'),
    validators=[username_validator],
    error_messages={
      'unique': gettext_lazy('A user with that username already exists.'),
    }
  )
  screen_name = models.CharField(
    gettext_lazy('screen name'),
    max_length=128,
    blank=True,
    help_text=gettext_lazy('Option. 128 characters or fewer.'),
  )
  email = models.EmailField(gettext_lazy('email address'), unique=True)
  is_staff = models.BooleanField(
    gettext_lazy('staff status'),
    default=False,
    help_text=gettext_lazy('Designates whether the user can log into this admin site.'),
  )
  is_active = models.BooleanField(
    gettext_lazy('active'),
    default=True,
    help_text=gettext_lazy(
      'Designates whether this user should be treated as active. Unselect this instead of deleting accounts.'
    )
  )
  date_joined = models.DateTimeField(gettext_lazy('date joined'), default=timezone.now)

  objects = CustomUserManager()

  EMAIL_FIELD = 'email'
  USERNAME_FIELD = 'username'
  REQUIRED_FIELDS = ['email']

  class Meta:
    verbose_name = gettext_lazy('user')
    verbose_name_plural = gettext_lazy('users')

  def __str__(self):
    return self.screen_name or self.username

  def get_full_name(self):
    return str(self)

  def get_short_name(self):
    max_len = 32
    full_name = self.get_full_name()

    if len(full_name) > max_len:
      short_name = '{}...'.format(full_name[:max_len])
    else:
      short_name = full_name

    return short_name