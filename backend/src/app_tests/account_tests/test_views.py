import pytest
from dataclasses import dataclass
from django.contrib.auth import get_user_model
from django.urls import reverse
from app_tests import status, factories

UserModel = get_user_model()

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestIndexLoginLogout:
  index_url = reverse('account:index')
  login_url = reverse('account:login')
  logout_url = reverse('account:logout')

  def test_index_view_get_access(self, client):
    response = client.get(self.index_url)

    assert response.status_code == status.HTTP_200_OK

  def test_login_view_get_access(self, client):
    response = client.get(self.login_url)

    assert response.status_code == status.HTTP_200_OK

  def test_login_view_post_access(self, get_user_with_option, client):
    option, _ = get_user_with_option
    params = {
      'username': option['username'],
      'password': option['password'],
    }
    response = client.post(self.login_url, params)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.index_url

  def test_logout_page(self, get_user_with_option, client):
    _, user = get_user_with_option
    client.force_login(user)
    response = client.post(self.logout_url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.index_url

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestUserProfile:
  profile_url = lambda _self, pk: reverse('account:user_profile', kwargs={'pk': pk})
  update_profile_url = lambda _self, pk: reverse('account:update_profile', kwargs={'pk': pk})

  def test_with_authenticated_client_for_user_profile(self, get_user_with_option, client):
    _, user = get_user_with_option
    client.force_login(user)
    response = client.get(self.profile_url(user.pk))

    assert response.status_code == status.HTTP_200_OK

  def test_without_authentication_for_user_profile(self, get_user_with_option, client):
    _, user = get_user_with_option
    response = client.get(self.profile_url(user.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_invalid_user_profile_page(self, get_user_with_option, client):
    _, owner = get_user_with_option
    other = factories.UserFactory()
    client.force_login(owner)
    response = client.get(self.profile_url(other.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_access_to_update_user_profile_page(self, get_user_with_option, client):
    _, user = get_user_with_option
    user.screen_name = 'test-user-profile'
    user.save()
    client.force_login(user)
    response = client.get(self.update_profile_url(user.pk))

    assert response.status_code == status.HTTP_200_OK

  def test_update_user_profile(self, get_user_with_option, client):
    _, user = get_user_with_option
    new_name = 'new-name'
    user.screen_name = 'old-name'
    user.save()
    client.force_login(user)
    response = client.post(self.update_profile_url(user.pk), data={'screen_name': new_name})
    updated_user = UserModel.objects.get(pk=user.pk)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.profile_url(user.pk)
    assert updated_user.screen_name == new_name