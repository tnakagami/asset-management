from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailBackend(ModelBackend):
  def authenticate(self, request, username=None, password=None, **kwargs):
    try:
      user = User.objects.get(Q(username__iexact=username) | Q(email__iexact=username))
      valid_user = user if user.check_password(password) and self.user_can_authenticate(user) else None
    except User.DoesNotExist:
      valid_user = None

    return valid_user

  def get_user(self, user_id):
    try:
      user = User.objects.get(pk=user_id)
      valid_user = user if self.user_can_authenticate(user) else None
    except User.DoesNotExist:
      valid_user = None

    return valid_user