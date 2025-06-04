from django.contrib.auth import get_user_model

empty_qs = get_user_model().objects.none()