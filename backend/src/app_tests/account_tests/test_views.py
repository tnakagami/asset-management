import pytest
from dataclasses import dataclass
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from app_tests import status, factories, get_date

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

  def test_portfolio_context_stats(self, client):
    user = factories.UserFactory()
    industry_defensive = factories.IndustryFactory(is_defensive=True)
    stock_a = factories.StockFactory(
      industry=industry_defensive,
      price=Decimal('1000.00'),
      dividend=Decimal('50.00'),
    )
    factories.PurchasedStockFactory(
      user=user,
      stock=stock_a,
      price=Decimal('1000.00'),
      count=10,
      purchase_date=get_date((2023, 10, 11)),
      has_been_sold=False,
    )
    industry_non_defensive = factories.IndustryFactory(is_defensive=False)
    stock_b = factories.StockFactory(
      industry=industry_non_defensive,
      price=Decimal('2000.00'),
      dividend=Decimal('100.00'),
    )
    factories.PurchasedStockFactory(
      user=user,
      stock=stock_b,
      price=Decimal('2000.00'),
      count=20,
      purchase_date=get_date((2023, 10, 12)),
      has_been_sold=False,
    )
    stock_c = factories.StockFactory(
      industry=industry_non_defensive,
      price=Decimal('3000.00'),
      dividend=Decimal('150.00'),
    )
    factories.PurchasedStockFactory(
      user=user,
      stock=stock_c,
      price=Decimal('3000.00'),
      count=5,
      purchase_date=get_date((2023, 10, 13)),
      has_been_sold=True,
    )
    # ------------
    # main routine
    # ------------
    client.force_login(user)
    response = client.get(self.profile_url(user.pk))
    owner = response.context['owner']
    stats = list(owner.industry_stats)

    assert response.status_code == 200
    assert owner.purchased_stock_count == 2
    assert owner.total_investment_amount == Decimal('50000.00')
    assert owner.total_annual_dividend == Decimal('2500.00')
    assert len(stats) == 2
    assert stats[0]['industry_pk'] == industry_defensive.pk
    assert stats[0]['is_defensive']
    assert stats[0]['industry_stock_count'] == 1
    assert stats[0]['industry_investment'] == Decimal('10000.00')
    assert stats[0]['industry_dividend'] == Decimal('500.00')
    assert stats[1]['industry_pk'] == industry_non_defensive.pk
    assert not stats[1]['is_defensive']
    assert stats[1]['industry_stock_count'] == 1
    assert stats[1]['industry_investment'] == Decimal('40000.00')
    assert stats[1]['industry_dividend'] == Decimal('2000.00')