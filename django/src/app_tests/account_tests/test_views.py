import pytest
from dataclasses import dataclass
from django.urls import reverse
from django.contrib.auth import get_user_model
from app_tests import status

User = get_user_model()

@dataclass
class _UserInfo:
  username: str
  email: str
  password: str
  user: User

@pytest.fixture
def init_records(django_db_blocker):
  # First user
  hoge = {
    'username': 'hoge',
    'email': 'hoge@example.com',
    'password': 'password1',
  }
  # Second user
  foo = {
    'username': 'foo',
    'email': 'foo@example.com',
    'password': 'password2',
  }

  with django_db_blocker.unblock():
    users = [
      _UserInfo(**hoge, user=User.objects.create_user(**hoge)),
      _UserInfo(**foo, user=User.objects.create_user(**foo))
    ]

  return users

@pytest.mark.account
@pytest.mark.view
def test_index_view_get_access(client):
  url = reverse('account:index')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
def test_login_view_get_access(client):
  url = reverse('account:login')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_login_view_post_access(init_records, client):
  user = init_records[0]
  params = {
    'username': user.username,
    'password': user.password,
  }
  url = reverse('account:login')
  response = client.post(url, params)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse('account:index')

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authenticated_client_for_user_profile(init_records, client):
  info = init_records[0]
  client.force_login(info.user)
  url = reverse('account:user_profile', kwargs={'pk': info.user.pk})
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_without_authentication_for_user_profile(init_records, client):
  info = init_records[0]
  url = reverse('account:user_profile', kwargs={'pk': info.user.pk})
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_user_profile_page(init_records, client):
  own = init_records[0]
  other = init_records[1]
  client.force_login(own.user)
  url = reverse('account:user_profile', kwargs={'pk': other.user.pk})
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_access_to_update_user_profile_page(init_records, client):
  screen_name = 'test-user-profile'
  user = init_records[0].user
  user.screen_name = screen_name
  user.save()
  url = reverse('account:update_profile', kwargs={'pk': user.pk})
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_update_user_profile(init_records, client):
  old_name = 'old-name'
  new_name = 'new-name'
  user = init_records[0].user
  user.screen_name = old_name
  user.save()
  url = reverse('account:update_profile', kwargs={'pk': user.pk})
  client.force_login(user)
  response = client.post(url, data={'screen_name': new_name})
  modified_user = User.objects.get(pk=user.pk)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse('account:user_profile', kwargs={'pk': user.pk})
  assert modified_user.screen_name == new_name

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_logout_page(init_records, client):
  info = init_records[0]
  client.force_login(info.user)
  url = reverse('account:logout')
  response = client.post(url)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse('account:index')