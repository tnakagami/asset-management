import pytest
import csv
import json
import urllib.parse
from io import StringIO
from webtest.app import AppError
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.utils.translation import gettext_lazy
from django.urls import reverse
from decimal import Decimal
from app_tests import (
  status,
  factories,
  get_date,
  BaseTestUtils,
)
from stock import models

UserModel = get_user_model()

# Get current path based on request parameter
def get_current_path(response):
  return response.context['request'].path

class SharedFixture(BaseTestUtils):
  @pytest.fixture
  def init_webtest(self, django_db_blocker, csrf_exempt_django_app):
    with django_db_blocker.unblock():
      owner, other = factories.UserFactory.create_batch(2)
    app = csrf_exempt_django_app
    users = {
      'owner': owner,
      'other': other,
    }

    return app, users

# ===================
# Account application
# ===================
@pytest.mark.webtest
@pytest.mark.django_db
class TestAccountApplication(SharedFixture):
  index_url = reverse('account:index')
  login_url = reverse('account:login')
  profile_url = lambda _self, pk: reverse('account:user_profile', kwargs={'pk': pk})
  update_profile_url = lambda _self, pk: reverse('account:update_profile', kwargs={'pk': pk})

  def test_access_to_index_page(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    response = app.get(self.index_url)

    assert response.status_code == status.HTTP_200_OK
    assert 'Index' in str(response)

  def test_move_to_login_page(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    page = app.get(self.index_url)
    response = page.click('Login')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.login_url

  @pytest.mark.parametrize([
    'arg_type'
  ], [
    ('username',),
    ('email', )
  ], ids=lambda val: f'login-{val}')
  def test_login_procedure(self, csrf_exempt_django_app, arg_type):
    app = csrf_exempt_django_app
    params = {
      'username': 'test-user',
      'email': 'user@test.com',
      'password': 'test-password',
    }
    user = UserModel.objects.create_user(**params)
    # Get form and submit form
    forms = app.get(self.login_url).forms
    form = forms['login-form']
    form['username'] = params[arg_type]
    form['password'] = params['password']
    response = form.submit().follow()

    assert response.context['user'].username == params['username']

  def test_move_to_parent_page_from_login_page(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    page = app.get(self.login_url)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.index_url

  @pytest.mark.webtest
  @pytest.mark.django_db
  def test_logout_procedure(self, init_webtest):
    app, users = init_webtest
    # Get form and submit form
    forms = app.get(self.index_url, user=users['owner']).forms
    form = forms['logout-form']
    response = form.submit().follow()

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.index_url

  # User profile page
  def test_move_to_user_profile_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    page = app.get(self.index_url, user=owner)
    response = page.click('User Profile')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.profile_url(owner.pk)

  def test_move_to_previous_page_from_user_profile_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    page = app.get(self.profile_url(owner.pk), user=owner)
    response = page.click('Back')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.index_url

  # Update user profile page
  def test_move_to_update_user_profile_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    pk = owner.pk
    page = app.get(self.profile_url(pk), user=owner)
    response = page.click('Update user profile')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.update_profile_url(pk)

  def test_update_user_profile(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    params = {
      'username': 'test-user',
      'email': 'user@test.com',
      'screen_name': 'sample',
    }
    new_screen_name = 'updated-name'
    user = factories.UserFactory(**params)
    pk = user.pk
    # Get form and submit form
    forms = app.get(self.update_profile_url(pk), user=user).forms
    form = forms['user-profile-form']
    form['screen_name'] = new_screen_name
    response = form.submit().follow()
    new_user = response.context['user']

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.profile_url(pk)
    assert new_user.username == params['username']
    assert new_user.email == params['email']
    assert new_user.screen_name == new_screen_name

  def test_move_to_parent_page_from_update_user_profile_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    pk = owner.pk
    page = app.get(self.update_profile_url(pk), user=owner)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.profile_url(pk)

  # =============
  # Invalid cases
  # =============
  @pytest.mark.parametrize([
    'page_link',
    'method',
    'params',
  ], [
    ('user_profile',   'get',  {}),
    ('update_profile', 'get',  {}),
    ('update_profile', 'post', {'screen_name': 'invalid-name'}),
  ], ids=[
    'user-profile-by-using-get-method',
    'update-user-profile-by-using-get-method',
    'update-user-profile-by-using-post-method',
  ])
  def test_invalid_page_access(self, init_webtest, page_link, method, params):
    app, users = init_webtest

    with pytest.raises(AppError) as ex:
      url = reverse(f'account:{page_link}', kwargs={'pk': users['other'].pk})
      caller = getattr(app, method)
      caller(url, params=params, user=users['owner'])

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

# =================
# Stock application
# =================
class BaseStockTestUtils(SharedFixture):
  index_url = reverse('account:index')
  login_url = reverse('account:login')
  dashboard_url = reverse('stock:dashboard')
  history_url  = reverse('stock:investment_history')
  # Cash
  cash_list_url = reverse('stock:list_cash')
  cash_create_url = reverse('stock:register_cash')
  cash_update_url = lambda _self, pk: reverse('stock:update_cash', kwargs={'pk': pk})
  cash_delete_url = lambda _self, pk: reverse('stock:delete_cash', kwargs={'pk': pk})
  # Purchased stock
  pstock_list_url = reverse('stock:list_purchased_stock')
  pstock_create_url = reverse('stock:register_purchased_stock')
  pstock_update_url = lambda _self, pk: reverse('stock:update_purchased_stock', kwargs={'pk': pk})
  pstock_delete_url = lambda _self, pk: reverse('stock:delete_purchased_stock', kwargs={'pk': pk})
  pstock_upload_url = reverse('stock:upload_purchased_stock_csv')
  pstock_download_url = reverse('stock:download_purchased_stock_csv')
  # Snapshot
  snapshot_list_url = reverse('stock:list_snapshot')
  snapshot_create_url = reverse('stock:register_snapshot')
  snapshot_update_url = lambda _self, pk: reverse('stock:update_snapshot', kwargs={'pk': pk})
  snapshot_delete_url = lambda _self, pk: reverse('stock:delete_snapshot', kwargs={'pk': pk})
  snapshot_detail_url = lambda _self, pk: reverse('stock:detail_snapshot', kwargs={'pk': pk})
  snapshot_upload_jsonformat_url = reverse('stock:upload_jsonformat_snapshot')
  snapshot_download_csv_url = lambda _self, pk: reverse('stock:download_csv_snapshot', kwargs={'pk': pk})
  snapshot_download_json_url = lambda _self, pk: reverse('stock:download_json_snapshot', kwargs={'pk': pk})
  # Periodic task for snapshot
  ptask_snapshot_list_url = reverse('stock:list_snapshot_task')
  ptask_snapshot_create_url = reverse('stock:register_snapshot_task')
  ptask_snapshot_update_url = lambda _self, pk: reverse('stock:update_snapshot_task', kwargs={'pk': pk})
  ptask_snapshot_delete_url = lambda _self, pk: reverse('stock:delete_snapshot_task', kwargs={'pk': pk})
  # Stock
  list_stock_url = reverse('stock:list_stock')
  download_stock_url = reverse('stock:download_stock')
  # Explanation
  explanation_url = reverse('stock:explanation')

@pytest.mark.webtest
@pytest.mark.django_db
class TestPageTransition(BaseStockTestUtils):
  @pytest.mark.parametrize([
    'page_title',
    'access_link',
  ], [
    ('Dashboard', 'dashboard_url'),
    ('Investment history', 'history_url'),
    ('Cash list', 'cash_list_url'),
    ('Purchased stock list', 'pstock_list_url'),
    ('Snapshot list', 'snapshot_list_url'),
    ('Periodic task list for snapshot', 'ptask_snapshot_list_url'),
    ('Stock list', 'list_stock_url'),
    ('Explanation', 'explanation_url'),
  ], ids=[
    'dashboard-page',
    'history-page',
    'cash-list-page',
    'purchased-stock-list-page',
    'snapshot-list-page',
    'periodic-task-for-snapshot-list-page',
    'stock-list-page',
    'explanation-page',
  ])
  def test_move_to_link_from_index(self, init_webtest, page_title, access_link):
    app, users = init_webtest
    # Access to target page
    page = app.get(self.index_url, user=users['owner'])
    response = page.click(page_title)
    target_url = getattr(self, access_link)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == target_url

  @pytest.mark.parametrize([
    'base_link',
    'page_title',
    'access_link',
  ], [
    # from list page to create page
    ('dashboard_url', 'Register snapshot', 'snapshot_create_url'),
    ('history_url', 'Register snapshot', 'snapshot_create_url'),
    ('cash_list_url', 'Register cash', 'cash_create_url'),
    ('pstock_list_url', 'Register purchased stock', 'pstock_create_url'),
    ('snapshot_list_url', 'Register snapshot', 'snapshot_create_url'),
    # from create page to list page
    ('cash_create_url', 'Cancel', 'cash_list_url'),
    ('pstock_create_url', 'Cancel', 'pstock_list_url'),
    ('snapshot_create_url', 'Cancel', 'snapshot_list_url'),
    ('ptask_snapshot_create_url', 'Cancel', 'ptask_snapshot_list_url'),
  ], ids=[
    'register-page-from-dashboard-page',
    'register-page-from-history-page',
    'register-page-from-cash-list-page',
    'register-page-from-purchased-stock-list-page',
    'register-page-from-snapshot-list-page',
    'list-page-from-cash-registration-page',
    'list-page-from-purchased-stock-registration-page',
    'list-page-from-snapshot-registration-page',
    'list-page-from-periodic-task-registration-page',
  ])
  def test_move_to_link_between_list_page_and_create_page(self, init_webtest, base_link, page_title, access_link):
    app, users = init_webtest
    # Access to target page
    page = app.get(getattr(self, base_link), user=users['owner'])
    response = page.click(page_title)
    target_url = getattr(self, access_link)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == target_url

  @pytest.mark.parametrize([
    'ss_exist',
    'page_title',
    'access_link',
  ], [
    (True, 'Register periodic task for snapshot', 'ptask_snapshot_create_url'),
    (False, 'Register snapshot', 'snapshot_create_url'),
  ], ids=[
    'snapshot-exits',
    'snapshot-doesnot-exit',
  ])
  def test_move_to_create_page_from_ptask_list_page(self, init_webtest, ss_exist, page_title, access_link):
    app, users = init_webtest
    owner = users['owner']

    if ss_exist:
      _ = factories.SnapshotFactory(user=owner)
    # Access to target page
    page = app.get(self.ptask_snapshot_list_url, user=owner)
    response = page.click(page_title)
    target_url = getattr(self, access_link)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == target_url

  @pytest.mark.parametrize([
    'base_link',
    'access_link',
    'factory_class',
  ], [
    ('cash_list_url',     'cash_update_url',     factories.CashFactory),
    ('pstock_list_url',   'pstock_update_url',   factories.PurchasedStockFactory),
    ('snapshot_list_url', 'snapshot_update_url', factories.SnapshotFactory),
  ], ids=[
    'update-cash-page-from-list-page',
    'update-purchased-stock-page-from-list-page',
    'update-snapshot-page-from-list-page',
  ])
  def test_move_to_update_page_from_list_page(self, init_webtest, base_link, access_link, factory_class):
    app, users = init_webtest
    owner = users['owner']
    instance = factory_class(user=owner)
    from_url = getattr(self, base_link)
    get_link = getattr(self, access_link)
    target_url = get_link(instance.pk)
    # Access to target page
    page = app.get(from_url, user=owner)
    response = page.click(href=target_url)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == target_url

  def test_move_to_update_page_from_ptask_list_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    ss = factories.SnapshotFactory(user=owner)
    params = json.dumps({'user_pk': owner.pk, 'snapshot_pk': ss.pk})
    instance = factories.PeriodicTaskFactory(kwargs=params)
    target_url = self.ptask_snapshot_update_url(instance.pk)
    # Access to target page
    page = app.get(self.ptask_snapshot_list_url, user=owner)
    response = page.click(href=target_url)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == target_url

  @pytest.mark.parametrize([
    'base_link',
    'access_link',
    'factory_class',
  ], [
    # from update page to list page
    ('cash_update_url',     'cash_list_url',     factories.CashFactory),
    ('pstock_update_url',   'pstock_list_url',   factories.PurchasedStockFactory),
    ('snapshot_update_url', 'snapshot_list_url', factories.SnapshotFactory),
  ], ids=[
    'cash-list-page-from-update-page',
    'purchased-stock-list-page-from-update-page',
    'snapshot-list-page-from-update-page',
  ])
  def test_move_to_list_page_from_update_page(self, init_webtest, base_link, access_link, factory_class):
    app, users = init_webtest
    owner = users['owner']
    instance = factory_class(user=owner)
    get_link = getattr(self, base_link)
    from_url = get_link(instance.pk)
    target_url = getattr(self, access_link)
    # Access to target page
    page = app.get(from_url, user=owner)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == target_url

  def test_move_to_list_page_from_ptask_update_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    ss = factories.SnapshotFactory(user=owner)
    params = json.dumps({'user_pk': owner.pk, 'snapshot_pk': ss.pk})
    instance = factories.PeriodicTaskFactory(kwargs=params)
    page = app.get(self.ptask_snapshot_update_url(instance.pk), user=owner)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.ptask_snapshot_list_url

  # =============
  # Invalid cases
  # =============
  # Login without authentication
  @pytest.mark.parametrize([
    'access_link',
  ], [
    ('dashboard_url',),
    ('history_url',),
    ('cash_list_url',),
    ('pstock_list_url',),
    ('snapshot_list_url',),
    ('ptask_snapshot_list_url',),
    ('pstock_upload_url',),
    ('snapshot_upload_jsonformat_url',),
    ('list_stock_url',),
  ], ids=[
    'dashboard-page',
    'history-page',
    'cash-list-page',
    'purchased-stock-list-page',
    'snapshot-list-page',
    'periodic-task-for-snapshot-list-page',
    'purchased-stock-upload-page',
    'snapshot-upload-jsonformat-page',
    'list-stock-page',
  ])
  def test_redirect_login_page_without_authentication(self, csrf_exempt_django_app, access_link):
    app = csrf_exempt_django_app
    response = app.get(getattr(self, access_link)).follow()

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.login_url

  # Go to create page without authentication
  @pytest.mark.parametrize([
    'access_link',
  ], [
    ('cash_create_url',),
    ('pstock_create_url',),
    ('snapshot_create_url',),
    ('ptask_snapshot_create_url',),
  ], ids=[
    'cash-registration-page',
    'purchased-stock-registration-page',
    'snapshot-registration-page',
    'periodic-task-for-snapshot-registration-page',
  ])
  def test_cannot_move_to_target_page_without_authentication(self, csrf_exempt_django_app, access_link):
    app = csrf_exempt_django_app

    with pytest.raises(AppError) as ex:
      app.get(getattr(self, access_link))

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  @pytest.mark.parametrize([
    'access_link',
    'factory_class',
  ], [
    ('cash_update_url', factories.CashFactory),
    ('pstock_update_url', factories.PurchasedStockFactory),
    ('snapshot_update_url', factories.SnapshotFactory),
  ], ids=[
    'invalid-access-to-update-cash-page',
    'invalid-access-to-update-purchased-stock-page',
    'invalid-access-to-update-snapshot-page',
  ])
  def test_cannot_access_update_page_except_owner(self, init_webtest, access_link, factory_class):
    app, users = init_webtest
    owner = users['owner']
    other = users['other']
    instance = factory_class(user=owner)

    with pytest.raises(AppError) as ex:
      get_link = getattr(self, access_link)
      app.get(get_link(instance.pk), user=other)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  # Go to update page by the other user
  def test_cannot_access_to_ptask_update_page_except_owner(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    other = users['other']
    snapshot = factories.SnapshotFactory(user=owner)
    instance = factories.PeriodicTaskFactory(
      name='periodic-task-v5',
      enabled=False,
      kwargs=json.dumps({'user_pk': owner.pk, 'snapshot_pk': snapshot.pk}),
      crontab=factories.CrontabScheduleFactory(minute=23, hour=10),
    )

    with pytest.raises(AppError) as ex:
      app.get(self.ptask_snapshot_update_url(instance.pk), user=other)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

@pytest.mark.webtest
@pytest.mark.django_db
class TestStockAppOperation(BaseStockTestUtils):
  # =========
  # List page
  # =========
  @pytest.mark.parametrize([
    'access_link',
    'object_name',
    'factory_class',
  ], [
    ('cash_list_url',     'cashes',    factories.CashFactory),
    ('pstock_list_url',   'pstocks',   factories.PurchasedStockFactory),
    ('snapshot_list_url', 'snapshots', factories.SnapshotFactory),
  ], ids=[
    'count-cashes',
    'count-pstocks',
    'count-snapshots',
  ])
  def test_count_owned_items(self, init_webtest, access_link, object_name, factory_class):
    app, users = init_webtest
    owner = users['owner']
    other = users['other']
    # Create instances
    for (target_user, num) in [(owner, 2), (other, 3)]:
      _ = factories.CashFactory.create_batch(num, user=target_user)
    # Access to link
    response = app.get(self.cash_list_url, user=owner)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.context['cashes']) == 2

  def test_count_own_ptask_items(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    other = users['other']
    # Create instances
    for (current, name) in [(owner, 'owner'), (other, 'other')]:
      for title_suffix in ['1st', '2nd']:
        ss = factories.SnapshotFactory(user=current, title=f'{name}_{title_suffix}')
        params = json.dumps({'user_pk': current.pk, 'snapshot_pk': ss.pk})
        _ = factories.PeriodicTaskFactory(kwargs=params)
    # Access to link
    response = app.get(self.ptask_snapshot_list_url, user=owner)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.context['tasks']) == 2

  @pytest.fixture(scope='class')
  def get_pseudo_purchased_stocks(self, django_db_blocker):
    with django_db_blocker.unblock():
      user = factories.UserFactory()
      industry = factories.IndustryFactory()
      stocks = [
        factories.StockFactory(code='NH3',    price=1000, industry=industry),
        factories.StockFactory(code='XYZ123', price=1200, industry=industry),
        factories.StockFactory(code='003ijk', price=1300, industry=industry),
      ]
      configs = [
        {'stock': stocks[2], 'price': 1000, 'purchase_date': get_date((2000, 1, 1))},
        {'stock': stocks[1], 'price': 1150, 'purchase_date': get_date((2000, 1, 1))},
        {'stock': stocks[0], 'price': 1500, 'purchase_date': get_date((2001, 1, 1))},
        {'stock': stocks[2], 'price': 1050, 'purchase_date': get_date((2003, 1, 1))},
      ]
      purchased_stocks = [factories.PurchasedStockFactory(user=user, count=1, **conf) for conf in configs]

    return user, purchased_stocks

  @pytest.mark.parametrize([
    'condition',
    'indices',
  ], [
    ('purchase_date < "2002-01-01T09:00+09:00"', [2, 0, 1]),
    ('price > 1100', [2, 1]),
    ('diff < 0', [2]),
    ('code == "003ijk" and price > 1025', [3]),
  ], ids=[
    'purchase-date-condition',
    'price-condition',
    'diff-condition',
    'multi-conditions',
  ])
  def test_filtering_purchased_stocks(self, csrf_exempt_django_app, get_pseudo_purchased_stocks, condition, indices):
    user, all_pstocks = get_pseudo_purchased_stocks
    targets = [all_pstocks[idx] for idx in indices]
    expected_pstocks = models.PurchasedStock.objects.filter(pk__in=self.get_pks(targets))
    app = csrf_exempt_django_app
    # Execution
    forms = app.get(self.pstock_list_url, user=user).forms
    form = forms['record-filtering-form']
    form['condition'] = condition
    response = form.submit()
    # Collect response data
    records = response.context['pstocks']

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.pstock_list_url
    assert len(records) == len(expected_pstocks)
    assert all([estimated.pk == expected.pk for estimated, expected in zip(records, expected_pstocks)])

  # ===========
  # Create page
  # ===========
  @pytest.fixture(scope='class')
  def get_dummy_stock(self, django_db_blocker):
    with django_db_blocker.unblock():
      industry = factories.IndustryFactory()
      _ = factories.LocalizedIndustryFactory(language_code='en', industry=industry)
      stock = factories.StockFactory(code='a9028', industry=industry)
      _ = factories.LocalizedStockFactory(language_code='en', stock=stock)

    return stock

  @pytest.fixture(params=['cash', 'pstock', 'snapshot'])
  def get_form_params_in_create_page(self, request, get_dummy_stock):
    key = request.param

    if key == 'cash':
      config = {
        'target': key,
        'access_link': self.cash_create_url,
        'form_id': 'cash-form',
        'success_link': self.cash_list_url,
      }
      params = {
        'balance': 1023,
        'registered_date': '2023-3-5',
      }
      object_name = 'cashes'
      exacts = {
        'balance': '1,023',
        'registeredDate': '2023-03-05',
      }
    elif key == 'pstock':
      stock = get_dummy_stock
      config = {
        'target': key,
        'access_link': self.pstock_create_url,
        'form_id': 'purchased-stock-form',
        'success_link': self.pstock_list_url,
        'stock': stock,
      }
      params = {
        'stock': stock.pk,
        'price': 4356.78,
        'purchase_date': '2024-9-22',
        'count': 100,
      }
      object_name = 'pstocks'
      exacts = {
        'code': stock.code,
        'name': stock.get_name(),
        'industry': str(stock.industry),
        'purchaseDate': '2024-09-22',
        'price': '4,356.78',
        'count': '100',
      }
    elif key == 'snapshot':
      config = {
        'target': key,
        'access_link': self.snapshot_create_url,
        'form_id': 'snapshot-form',
        'success_link': self.snapshot_list_url,
      }
      params = {
        'title': 'sample-snapshot',
        'start_date': '2024-12-3',
        'end_date': '2025-1-21',
      }
      object_name = 'snapshots'
      exacts = {
        'title': 'sample-snapshot',
        'startDate': '2024-12-03',
        'endDate': '2025-01-21',
      }

    return config, params, object_name, exacts

  def test_creation_form(self, mocker, get_form_params_in_create_page, init_webtest):
    mocker.patch('stock.models.get_language', return_value='en')
    config, params, object_name, exacts = get_form_params_in_create_page

    # ------------
    # main routine
    # ------------
    app, users = init_webtest
    forms = app.get(config['access_link'], user=users['owner']).forms
    form = forms[config['form_id']]
    # Update form data
    for key, val in params.items():
      form[key] = val
    response = form.submit().follow()
    # Collect response data
    records = response.context[object_name]
    elements = {
      element.attrs['data-type']: element.get_text().strip()
      for element in response.html.find_all('td', attrs={'data-type': True})
    }

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == config['success_link']
    assert len(records) == 1
    assert all([elements[key] == _exactval for key, _exactval in exacts.items()])

  def test_periodic_task_creation_form(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    snapshot = factories.SnapshotFactory(user=owner)
    forms = app.get(self.ptask_snapshot_create_url, user=owner).forms
    form = forms['task-form']
    # Setup form data and exact values
    params = {
      'name': 'sample-periodic-task-v2',
      'enabled': True,
      'snapshot': snapshot.pk,
      'schedule_type': 'every-day',
      'config': json.dumps({'minute': 23, 'hour': 13}),
    }
    exacts = {
      'taskName': params['name'],
      'snapshotName': snapshot.title,
      'schedule' : '23 13 * * * (m/h/dM/MY/d) UTC',
      'totalRunCount': '0',
      'isEnabled': 'Enabled',
    }
    # Update form data
    for key, val in params.items():
      form[key] = val
    response = form.submit().follow()
    # Collect response data
    records = response.context['tasks']
    elements = {
      element.attrs['data-type']: element.contents[0]
      for element in response.html.find_all('td', attrs={'data-type': True})
    }

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.ptask_snapshot_list_url
    assert len(records) == 1
    assert all([elements[key] == _exactval for key, _exactval in exacts.items()])

  # ===========
  # Update page
  # ===========
  @pytest.fixture
  def get_form_params_in_update_page(self, get_form_params_in_create_page):
    old_conf, old_params, object_name, old_exacts = get_form_params_in_create_page

    if old_conf['target'] == 'cash':
      config = {
        'get_link': self.cash_update_url,
        'factory': factories.CashFactory,
        'form_id': old_conf['form_id'],
        'success_link': old_conf['success_link'],
      }
      params = {
        'balance': old_params['balance'],
        'registered_date': f'{old_params["registered_date"]}T00:00:00+00:00',
      }
      updated = {
        'balance': 2048,
        'registered_date': '2022-10-1',
      }
      exacts = {
        'balance': '2,048',
        'registeredDate': '2022-10-01',
      }
    elif old_conf['target'] == 'pstock':
      config = {
        'get_link': self.pstock_update_url,
        'factory': factories.PurchasedStockFactory,
        'form_id': old_conf['form_id'],
        'success_link': old_conf['success_link'],
      }
      params = {
        'stock': old_conf['stock'],
        'price': Decimal(str(old_params['price'])),
        'purchase_date': f'{old_params["purchase_date"]}T00:00:00+00:00',
        'count': old_params['count'],
      }
      updated = {
        'stock': old_params['stock'],
        'price': Decimal('1052.01'),
        'purchase_date': '2012-8-17',
        'count': 2200,
      }
      exacts = {
        'code': old_exacts['code'],
        'name': old_exacts['name'],
        'industry': old_exacts['industry'],
        'purchaseDate': '2012-08-17',
        'price': '1,052.01',
        'count': '2,200',
      }
    elif old_conf['target'] == 'snapshot':
      config = {
        'get_link': self.snapshot_update_url,
        'factory': factories.SnapshotFactory,
        'form_id': old_conf['form_id'],
        'success_link': old_conf['success_link'],
      }
      params = {
        'title': old_params['title'],
        'start_date': f'{old_params["start_date"]}T00:00:00+00:00',
        'end_date': f'{old_params["end_date"]}T00:00:00+00:00',
      }
      updated = {
        'title': 'updated-snapshot',
        'start_date': '2010-1-4',
        'end_date': '2011-02-15',
      }
      exacts = {
        'title': 'updated-snapshot',
        'startDate': '2010-01-04',
        'endDate': '2011-02-15',
      }

    return config, params, updated, object_name, exacts

  def test_update_form(self, mocker, get_form_params_in_update_page, init_webtest):
    mocker.patch('stock.models.get_language', return_value='en')
    config, params, updated, object_name, exacts = get_form_params_in_update_page
    app, users = init_webtest
    owner = users['owner']

    # ------------
    # main routine
    # ------------
    # Preparation
    factory_class = config['factory']
    instance = factory_class(user=owner, **params)
    # Execution
    forms = app.get(config['get_link'](instance.pk), user=owner).forms
    form = forms[config['form_id']]
    for key, val in updated.items():
      form[key] = val
    response = form.submit().follow()
    # Collect response data
    records = response.context[object_name]
    elements = {
      element.attrs['data-type']: element.get_text().strip()
      for element in response.html.find_all('td', attrs={'data-type': True})
    }

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == config['success_link']
    assert len(records) == 1
    assert all([elements[key] == _exactval for key, _exactval in exacts.items()])

  def test_periodic_task_update_form(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    snapshot = factories.SnapshotFactory(user=owner)
    instance = factories.PeriodicTaskFactory(
      name='sample-periodic-task-v3',
      enabled=True,
      kwargs=json.dumps({'user_pk': owner.pk, 'snapshot_pk': snapshot.pk}),
      crontab=factories.CrontabScheduleFactory(minute=23, hour=10),
    )
    # Execution
    forms = app.get(self.ptask_snapshot_update_url(instance.pk), user=owner).forms
    form = forms['task-form']
    # Setup form data and exact values
    params = {
      'name': 'updated-periodic-task-v4',
      'enabled': False,
      'snapshot': snapshot.pk,
      'schedule_type': 'every-week',
      'config': json.dumps({'minute': 20, 'hour': 9, 'day_of_week': 'fri'}),
    }
    exact_vals = {
      'taskName': params['name'],
      'snapshotName': snapshot.title,
      'schedule' : '20 9 * * fri (m/h/dM/MY/d) UTC',
      'totalRunCount': '0',
      'isEnabled': 'Disabled',
    }
    # Update form data
    for key, val in params.items():
      form[key] = val
    response = form.submit().follow()
    # Collect response data
    records = response.context['tasks']
    elements = {
      element.attrs['data-type']: element.contents[0]
      for element in response.html.find_all('td', attrs={'data-type': True})
    }

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.ptask_snapshot_list_url
    assert len(records) == 1
    assert all([elements[key] == _exactval for key, _exactval in exact_vals.items()])

  # ===========
  # Delete page
  # ===========
  @pytest.mark.parametrize([
    'base_link',
    'target_link',
    'object_name',
    'factory_class',
  ], [
    ('cash_list_url',     'cash_delete_url',     'cashes',    factories.CashFactory),
    ('pstock_list_url',   'pstock_delete_url',   'pstocks',   factories.PurchasedStockFactory),
    ('snapshot_list_url', 'snapshot_delete_url', 'snapshots', factories.SnapshotFactory),
  ], ids=[
    'cash-update-page',
    'purchased-stock-update-page',
    'snapshot-update-page',
  ])
  def test_delete_form(self, init_webtest, base_link, target_link, object_name, factory_class):
    app, users = init_webtest
    owner = users['owner']
    target, rest = factory_class.create_batch(2, user=owner)
    url = getattr(self, base_link)
    forms = app.get(url, user=owner).forms
    form = forms['delete-form']
    get_link = getattr(self, target_link)
    form.action = get_link(target.pk)
    response = form.submit().follow()

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == url
    assert len(response.context[object_name]) == 1
    assert response.context[object_name].first().pk == rest.pk

  def test_periodic_task_delete_form(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    snapshots = factories.SnapshotFactory.create_batch(2, user=owner)
    crontab = factories.CrontabScheduleFactory(minute=23, hour=10)
    target = factories.PeriodicTaskFactory(
      name='periodic-task-for-deletion-ss1',
      enabled=False,
      kwargs=json.dumps({'user_pk': owner.pk, 'snapshot_pk': snapshots[0].pk}),
      crontab=crontab,
    )
    rest = factories.PeriodicTaskFactory(
      name='periodic-task-for-deletion-ss2',
      enabled=True,
      kwargs=json.dumps({'user_pk': owner.pk, 'snapshot_pk': snapshots[1].pk}),
      crontab=crontab,
    )
    url = self.ptask_snapshot_list_url
    forms = app.get(url, user=owner).forms
    form = forms['delete-form']
    form.action = self.ptask_snapshot_delete_url(target.pk)
    response = form.submit().follow()

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == url
    assert len(response.context['tasks']) == 1
    assert response.context['tasks'].first().pk == rest.pk

  # =============================
  # Dashboard page / history page
  # =============================
  @pytest.fixture(scope='class')
  def get_pseudo_cash_and_pstock_data(self, django_db_blocker):
    with django_db_blocker.unblock():
      user = factories.UserFactory()
      # Create cash
      _ = factories.CashFactory(user=user, balance=123456, registered_date=get_date((2010,2,3)))
      cash = factories.CashFactory(user=user, balance=234567, registered_date=get_date((2021,12,3)))
      # Create stocks
      stocks = []
      patterns = [
        ('ja', 'en', '420Ac1x', 'stock1'),
        ('en', 'ja', '3dcy4Az', 'stock2'),
      ]
      for ind_lang, stock_lang, code, name in patterns:
        industry = factories.IndustryFactory()
        _ = factories.LocalizedIndustryFactory(language_code=ind_lang, industry=industry)
        stock = factories.StockFactory(code=code, industry=industry)
        _ = factories.LocalizedStockFactory(name=name, language_code=stock_lang, stock=stock)
        stocks += [stock]
      # Create purchased stocks
      ps_data = []
      patterns = [
        (stocks[0], Decimal( '123.01'), (2022,  3,  2),  100, True),   # 1st purchased data
        (stocks[1], Decimal( '114.21'), (2021,  3,  4),  332, False),  # Skip
        (stocks[1], Decimal('1145.15'), (2021, 12,  9),  510, True),   # 3rd purchased data
        (stocks[0], Decimal( '245.89'), (2022,  3,  3),  540, False),  # Skip
        (stocks[0], Decimal('2345.99'), (2022,  1, 12), 1020, True),   # 2nd purchased data
      ]
      for stock, price, ymd, count, is_stored in patterns:
        purchased_stock = factories.PurchasedStockFactory(
          user=user, stock=stock, price=price, purchase_date=get_date(ymd), count=count,
        )
        if is_stored:
          ps_data += [purchased_stock]
      # Create snapshot
      snapshot = factories.SnapshotFactory(
        user=user, title='sample', start_date=get_date((2021, 3, 5)), end_date=get_date((2022, 3, 2)),
      )
      expected = {
        'cash': cash.get_dict(),
        'purchased_stocks': [
          ps_data[0].get_dict(),
          ps_data[2].get_dict(),
          ps_data[1].get_dict(),
        ],
      }
      ss_uuid = str(snapshot.uuid)

    return user, ss_uuid, expected

  @pytest.mark.parametrize([
    'target_link',
  ], [
    ('dashboard_url', ),
    ('history_url', ),
  ], ids=['dashboard-page', 'history-page'])
  def test_chech_snapshot_detail_in_asset_page(self, csrf_exempt_django_app, get_pseudo_cash_and_pstock_data, target_link):
    app = csrf_exempt_django_app
    user, ss_uuid, expected = get_pseudo_cash_and_pstock_data
    access_link = getattr(self, target_link)
    compare_dict = lambda _est_dict, _exact_dict: all([_est_dict[key] == val for key, val in _exact_dict.items()])
    # Execution
    response = app.get(access_link, user=user)
    element = response.html.find('script', id=ss_uuid)
    estimated = json.loads(element.contents[0])

    assert all([key in estimated.keys() for key in ['cash', 'purchased_stocks']])
    assert compare_dict(estimated['cash'], expected['cash'])
    assert all([
      compare_dict(est_dict, exact_dict)
      for est_dict, exact_dict in zip(estimated['purchased_stocks'], expected['purchased_stocks'])
    ])

  # ===============
  # Invalid pattern
  # ===============
  # Try to update the other user's instance
  @pytest.mark.parametrize([
    'target_link',
    'form_id',
    'factory_class',
  ], [
    ('cash_update_url',     'cash-form',            factories.CashFactory),
    ('pstock_update_url',   'purchased-stock-form', factories.PurchasedStockFactory),
    ('snapshot_update_url', 'snapshot-form',        factories.SnapshotFactory),
  ], ids=[
    'invalid-post-method-in-cash',
    'invalid-post-method-in-purchased-stock',
    'invalid-post-method-in-snapshot',
  ])
  def test_invalid_post_method_in_update_page(self, init_webtest, target_link, form_id, factory_class):
    app, users = init_webtest
    owner = users['owner']
    other = users['other']
    instance = factory_class(user=owner)
    get_link = getattr(self, target_link)
    forms = app.get(get_link(instance.pk), user=owner).forms
    form = forms[form_id]

    with pytest.raises(AppError) as ex:
      form.submit(user=other)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  # Try to update the other user's periodic task for snapshot instance
  def test_invalid_post_method_in_ptask_update_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    other = users['other']
    snapshot = factories.SnapshotFactory(user=owner)
    instance = factories.PeriodicTaskFactory(
      name='periodic-task-v6',
      enabled=False,
      kwargs=json.dumps({'user_pk': owner.pk, 'snapshot_pk': snapshot.pk}),
      crontab=factories.CrontabScheduleFactory(minute=23, hour=10),
    )
    forms = app.get(self.ptask_snapshot_update_url(instance.pk), user=owner).forms
    form = forms['task-form']

    with pytest.raises(AppError) as ex:
      form.submit(user=other)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  # Delete the other user's instance
  @pytest.fixture(params=['cash', 'pstock', 'snapshot'])
  def get_pseudo_records_to_check_delete_process(self, request):
    key = request.param

    if key == 'cash':
      factory_class = factories.CashFactory
      list_link = self.cash_list_url
      get_link = self.cash_delete_url
    elif key == 'pstock':
      factory_class = factories.PurchasedStockFactory
      list_link = self.pstock_list_url
      get_link = self.pstock_delete_url
    elif key == 'snapshot':
      factory_class = factories.SnapshotFactory
      list_link = self.snapshot_list_url
      get_link = self.snapshot_delete_url

    return list_link, get_link, factory_class

  def test_invalid_delete_request(self, init_webtest, get_pseudo_records_to_check_delete_process):
    app, users = init_webtest
    owner = users['owner']
    other = users['other']
    list_link, get_link, factory_class = get_pseudo_records_to_check_delete_process
    # Execution
    instance = factory_class(user=owner)
    forms = app.get(list_link, user=other).forms
    form = forms['delete-form']
    form.action = get_link(instance.pk)

    with pytest.raises(AppError) as ex:
      form.submit()

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  def test_invalid_request_for_deleting_ptask_instance(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    other = users['other']
    snapshot = factories.SnapshotFactory(user=owner)
    instance = factories.PeriodicTaskFactory(
      name='periodic-task-v6',
      enabled=False,
      kwargs=json.dumps({'user_pk': owner.pk, 'snapshot_pk': snapshot.pk}),
      crontab=factories.CrontabScheduleFactory(minute=23, hour=10),
    )
    forms = app.get(self.ptask_snapshot_list_url, user=other).forms
    form = forms['delete-form']
    form.action = self.ptask_snapshot_delete_url(instance.pk)

    with pytest.raises(AppError) as ex:
      form.submit()

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  # ====================
  # Detail snapshot page
  # ====================
  def test_access_to_detail_snapshot_page(self, init_webtest):
    pstock = {
      'stock': {
        'code': 'B3a42C',
        'names': {'en': 'en-bar', 'ge': 'ge-bar'},
        'industry': {
          'names': {'en': 'en-YYY', 'ge': 'ge-YYY'},
          'is_defensive': False,
        },
        'price':  800.00, 'dividend': 0, 'per': 0, 'pbr': 0,
        'eps': 0, 'bps': 0, 'roe': 0, 'er':  0,
      },
      'price': 500.00,
      'count': 200,
    }
    data = json.dumps({
      'cash': {'balance': 1700},
      'purchased_stocks': [pstock],
    })
    # Setup
    app, users = init_webtest
    owner = users['owner']
    instance = factories.SnapshotFactory(
      title='example-owner-snapshot',
      user=owner,
    )
    instance.detail = data
    instance.save()
    # Access to detail snapshot page
    page = app.get(self.snapshot_list_url, user=owner)
    response = page.click(instance.title)
    snapshot = response.context['snapshot']
    records = snapshot.create_records()

    assert response.status_code == status.HTTP_200_OK
    assert snapshot.pk == instance.pk
    assert len(records) == 2
    assert all([key in ['cash', 'B3a42C'] for key in records.keys()])
    assert abs(records['cash'].purchased_value - 1700.00) < 1e-6
    assert abs(records['B3a42C'].price - 800.00) < 1e-6
    assert abs(records['B3a42C'].purchased_value - 500.00*200) < 1e-6
    assert records['B3a42C'].count == 200

  def test_invalid_access_for_detail_snapshot_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    other = users['other']
    instance = factories.SnapshotFactory(user=owner)
    instance.save()
    # Invalid access for detail snapshot page
    with pytest.raises(AppError) as ex:
      app.get(self.snapshot_detail_url(instance.pk), user=other)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

@pytest.mark.webtest
@pytest.mark.django_db
class TestDownloadUploadOperation(BaseStockTestUtils):
  @pytest.fixture(scope='class')
  def get_sample_data_for_stock_search(self, django_db_blocker):
    with django_db_blocker.unblock():
      industries = [factories.IndustryFactory(), factories.IndustryFactory()]
      _ = factories.LocalizedIndustryFactory(name='alpha', language_code='en', industry=industries[0])
      _ = factories.LocalizedIndustryFactory(name='gamma', language_code='en', industry=industries[1])
      # Create Main stock data
      stocks = [
        factories.StockFactory(code='0B01', price=Decimal('1199.00'), roe=Decimal('1.03'), industry=industries[0]),
        factories.StockFactory(code='0B02', price=Decimal('1001.00'), roe=Decimal('2.03'), industry=industries[0]),
        factories.StockFactory(code='0B03', price=Decimal('1100.00'), roe=Decimal('3.03'), industry=industries[0]),
        factories.StockFactory(code='0B04', price=Decimal('2000.00'), roe=Decimal('1.03'), industry=industries[0]),
        factories.StockFactory(code='0B05', price=Decimal('1100.00'), roe=Decimal('1.03'), industry=industries[1]),
        factories.StockFactory(code='0B06', price=Decimal('1024.00'), roe=Decimal('1.51'), industry=industries[0], skip_task=True),
      ]
      # Create other stock data
      other_stocks  = factories.StockFactory.create_batch(151, price=1, industry=industries[1])
      # Add stock names
      for stock, name in zip(stocks, ['hogehoge', 'hoge-foo', 'bar', 'sample', 'test-stock5', 'skipped']):
        _ = factories.LocalizedStockFactory(name=name, language_code='en', stock=stock)
      for idx, stock in enumerate(other_stocks, len(stocks) + 1):
        name = f'stock-test{idx}'
        _ = factories.LocalizedStockFactory(name=name, language_code='en', stock=stock)
      # Collect all stock data
      all_stocks = stocks + other_stocks

    return all_stocks

  # ==============================
  # Upload purchased stocks as CSV
  # ==============================
  def test_move_to_pstock_csvfile_upload_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    page = app.get(self.pstock_list_url, user=owner)
    response = page.click('Upload purchased stocks as CSV')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.pstock_upload_url

  def test_move_to_parent_page_from_pstock_csvfile_upload_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    page = app.get(self.pstock_upload_url, user=owner)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.pstock_list_url

  @pytest.fixture(params=[
    ('utf-8',  True), ('shift_jis',  True), ('cp932',  True),
    ('utf-8', False), ('shift_jis', False), ('cp932', False),
  ], ids=[
    'utf8-with-header',    'sjis-with-header',    'cp932-with-header',
    'utf8-without-header', 'sjis-without-header', 'cp932-without-header',
  ])
  def get_valid_form_param_of_csvfile(self, request, get_sample_data_for_stock_search):
    encoding, has_header = request.param
    stocks = get_sample_data_for_stock_search
    # Create input data
    data = []
    if has_header:
      data += ['Code,Date,Price,Count']
    data += [
      f'{stocks[0].code},2024/9/17,2000,100',
      f'{stocks[1].code},2023-09-03,1000,200',
    ]
    # Create form data
    params = {
      'encoding': encoding,
      'header': has_header,
      'csv_file': ('test-file.csv', bytes('\n'.join(data) + '\n', encoding=encoding)), # For django-webtest format
    }
    exacts = [
      (stocks[0].code, '2024-09-17T00:00:00+00:00', 2000.00, 100),
      (stocks[1].code, '2023-09-03T00:00:00+00:00', 1000.00, 200),
    ]

    return params, exacts

  def test_send_post_request_to_upload_page(self, get_valid_form_param_of_csvfile, csrf_exempt_django_app):
    user = factories.UserFactory()
    params, exacts = get_valid_form_param_of_csvfile
    # Send request
    app = csrf_exempt_django_app
    forms = app.get(self.pstock_upload_url, user=user).forms
    form = forms['purchased-stock-upload-form']
    for key, val in params.items():
      form[key] = val
    response = form.submit().follow()
    # Collect expected queryset
    queryset = user.purchased_stocks.all()
    # Define checker
    def checker(obj, expected):
      out = all([
        models.convert_timezone(obj.purchase_date, is_string=True) == expected[1],
        abs(float(obj.price) - expected[2]) < 1e-2,
        obj.count == expected[3]
      ])

      return out

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.pstock_list_url
    assert len(queryset) == len(exacts)
    assert checker(queryset.get(stock__code=exacts[0][0]), exacts[0])
    assert checker(queryset.get(stock__code=exacts[1][0]), exacts[1])

  def test_send_invalid_encoding_in_upload_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    forms = app.get(self.pstock_upload_url, user=owner).forms
    form = forms['purchased-stock-upload-form']

    with pytest.raises(ValueError):
      form['encoding'] = 'euc-jp'

  def test_send_invalid_extensions_in_upload_page(self, init_webtest):
    params = {
      'encoding': 'utf-8',
      'header': False,
      'csv_file': ('hoge.txt', bytes('hogehoge\nfogafoga\n', 'utf-8')),
    }
    err_msg = 'The extention has to be &quot;.csv&quot;.'
    # Send request
    app, users = init_webtest
    owner = users['owner']
    forms = app.get(self.pstock_upload_url, user=owner).forms
    form = forms['purchased-stock-upload-form']
    for key, val in params.items():
      form[key] = val
    response = form.submit()
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

  @pytest.mark.parametrize([
    'exception_class',
    'err_msg',
  ], [
    (IntegrityError, 'Include invalid records. Please check the detail:'),
    (Exception, 'Unexpected error occurred:'),
  ], ids=['integrity-err', 'unexpected-err'])
  def test_exception_has_occurred_in_upload_page(self, mocker, get_valid_form_param_of_csvfile, init_webtest, exception_class, err_msg):
    mocker.patch('stock.models.PurchasedStock.objects.bulk_create', side_effect=exception_class('error'))
    params, _ = get_valid_form_param_of_csvfile
    app, users = init_webtest
    owner = users['owner']
    # Send request
    forms = app.get(self.pstock_upload_url, user=owner).forms
    form = forms['purchased-stock-upload-form']
    for key, val in params.items():
      form[key] = val
    response = form.submit()
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

  # ===========================================
  # Download purchased stocks by using csv file
  # ===========================================
  def test_check_download_pstock_for_csv_format(self, mocker, get_sample_data_for_stock_search, csrf_exempt_django_app):
    def get_data(obj):
      code = obj.stock.code
      date = models.convert_timezone(obj.purchase_date, is_string=True, strformat='%Y-%m-%d')
      price = '{:.2f}'.format(float(obj.price))
      count = '{}'.format(obj.count)
      out = [code, date, price, count]

      return out
    # Create expected data
    user = factories.UserFactory()
    stocks = get_sample_data_for_stock_search
    purchased_stocks = [
      factories.PurchasedStockFactory(
        user=user, stock=stocks[0], price=Decimal('123.41'),
        count=100, purchase_date=get_date((2022, 3, 4)),
      ),
      factories.PurchasedStockFactory(
        user=user, stock=stocks[2], price=Decimal('1000.00'),
        count=100, purchase_date=get_date((2021, 2, 1)),
      ),
      factories.PurchasedStockFactory(
        user=user, stock=stocks[1], price=512,
        count=300, purchase_date=get_date((2023, 5, 5)),
      ),
      factories.PurchasedStockFactory(
        user=user, stock=stocks[4], price=Decimal('512.01'),
        count=150, purchase_date=get_date((2022,10,15)),
      ),
    ]
    qs = models.PurchasedStock.objects.filter(pk__in=self.get_pks(purchased_stocks))
    # Mock
    mocker.patch('stock.models.generate_default_filename', return_value='20190124-120749')
    # Create expected data
    lines = '\n'.join([
      ','.join(get_data(obj))
      for obj in qs.order_by('-purchase_date')
    ])
    expected = {
      'rows': bytes(lines, 'utf-8'),
      'header': bytes('Code,Date,Price,Count', 'utf-8'),
      'filename': 'purchased-stock-20190124-120749.csv',
    }
    # Execution
    app = csrf_exempt_django_app
    page = app.get(self.pstock_list_url, user=user)
    response = page.click('Download purchased stocks as CSV')
    # Collect results
    attachment = response['content-disposition']
    stream = response.content

    assert expected['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert expected['header'] in stream
    assert expected['rows'] in stream

  # ===========================
  # Upload JSON format snapshot
  # ===========================
  def test_move_to_jsonfile_upload_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    page = app.get(self.snapshot_list_url, user=owner)
    response = page.click('Upload snapshot')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.snapshot_upload_jsonformat_url

  def test_move_to_parent_page_from_jsonfile_upload_page(self, init_webtest):
    app, users = init_webtest
    page = app.get(self.snapshot_upload_jsonformat_url, user=users['owner'])
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.snapshot_list_url

  @pytest.fixture(params=['utf-8', 'shift_jis', 'cp932'])
  def get_valid_form_param_of_jsonfile(self, request):
    encoding = request.param
    info = {
      'title': 'upload-json-file',
      'detail': {
        'cash': {
          'balance': 123,
          'registered_date': "2001-11-07T00:00:00+09:00",
        },
        'purchased_stocks': [{
          'stock': {},
          'price': 960.0,
          'purchase_date': "2000-12-27T00:00:00+09:00",
          'count': 145,
        }],
      },
      'priority': 99,
      'start_date': "2019-01-01T00:00:00+09:00",
      'end_date': "5364-12-30T00:00:00+09:00",
    }
    # Create form data
    params = {
      'encoding': encoding,
      'json_file': ('test-file.json', bytes(json.dumps(info), encoding=encoding)), # For django-webtest format
    }

    return params

  def test_post_request_from_jsonfile_upload_page(self, settings, get_valid_form_param_of_jsonfile, init_webtest):
    settings.TIME_ZONE = 'Asia/Tokyo'
    params = get_valid_form_param_of_jsonfile
    # Send request
    app, users = init_webtest
    owner = users['owner']
    forms = app.get(self.snapshot_upload_jsonformat_url, user=owner).forms
    form = forms['snapshot-upload-form']
    # Create inputs
    for key, val in params.items():
      form[key] = val
    response = form.submit().follow()
    # Collect expected queryset
    instance = models.Snapshot.objects.filter(user=owner, title__contains='upload-json-file').first()
    detail = json.loads(instance.detail)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.snapshot_list_url
    assert instance is not None
    assert instance.start_date.isoformat(timespec='seconds') == '2018-12-31T15:00:00+00:00'
    assert instance.end_date.isoformat(timespec='seconds') == '5364-12-29T15:00:00+00:00'
    assert instance.priority == 99
    assert detail['cash']['balance'] == 123
    assert len(detail['purchased_stocks']) == 1
    assert detail['purchased_stocks'][0]['count'] == 145

  def test_invalid_encoding_of_jsonfile_upload_page(self, init_webtest):
    app, users = init_webtest
    owner = users['owner']
    forms = app.get(self.snapshot_upload_jsonformat_url, user=owner).forms
    form = forms['snapshot-upload-form']

    with pytest.raises(ValueError):
      form['encoding'] = 'euc-jp'

  def test_send_invalid_extensions_of_jsonfile_upload_page(self, init_webtest):
    params = {
      'encoding': 'utf-8',
      'json_file': ('hoge.txt', bytes('{}', 'utf-8')),
    }
    err_msg = 'The extention has to be &quot;.json&quot;.'
    # Send request
    app, users = init_webtest
    owner = users['owner']
    forms = app.get(self.snapshot_upload_jsonformat_url, user=owner).forms
    form = forms['snapshot-upload-form']
    # Create inputs
    for key, val in params.items():
      form[key] = val
    response = form.submit()
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

  # Snapshot data to download it by csv/json format
  @pytest.fixture(scope='class')
  def get_download_data_of_pstock(self, django_db_blocker):
    industry_names = {'en': 'en-hoge', 'ja': '日本語-hoge'}
    pstock_names = {'en': 'en-234', 'ja': '日本語-234'}
    data = json.dumps({
      'cash': {'balance': 1700, 'registered_date': '2021-10-09'},
      'purchased_stocks': [{
        'stock': {
          'code': 'xyz314',
          'names': pstock_names,
          'industry': {
            'names': industry_names,
            'is_defensive': False,
          },
          'price': 650.00, 'dividend': 2.00, 'per': 1.73, 'pbr': 2.34,
          'eps': 0.52, 'bps': 2.11, 'roe': 0.12, 'er':  50.31,
        },
        'price': 500.00,
        'purchase_date': '2021-02-13',
        'count': 200,
      }],
    })
    # Create instances
    with django_db_blocker.unblock():
      user = factories.UserFactory()
      industry = factories.IndustryFactory(is_defensive=False)
      stock = factories.StockFactory(
        code='xyz314',
        industry=industry,
        price=Decimal('650.00'),
        dividend=Decimal('2.00'),
        per=Decimal('1.73'),
        pbr=Decimal('2.34'),
        eps=Decimal('0.52'),
        bps=Decimal('2.11'),
        roe=Decimal('0.12'),
        er=Decimal('50.31'),
      )
      # Create localized data
      for lang in ['en', 'ja']:
        _ = factories.LocalizedIndustryFactory(name=industry_names[lang], language_code=lang, industry=industry)
        _ = factories.LocalizedStockFactory(name=pstock_names[lang], language_code=lang, stock=stock)
      # Create cash
      cash = factories.CashFactory(
        user=user,
        balance=1700,
        registered_date=get_date((2021, 10, 9)),
      )
      # Create purchased stock
      purchased_stock = factories.PurchasedStockFactory(
        user=user,
        stock=stock,
        price=Decimal('500.00'),
        purchase_date=get_date((2021, 2, 13)),
        count=200,
      )
      # Create snapshot
      snapshot = factories.SnapshotFactory(
        user=user,
        title='今日のreport',
        priority=3,
        start_date=get_date((2020, 1, 15)),
        end_date=get_date((2022, 5, 6)),
      )
      snapshot.detail = data
      snapshot.save()

    return user, cash, purchased_stock, snapshot

  @pytest.fixture(params=['en', 'ja'])
  def get_test_data_of_download_snapshot(self, request, get_download_data_of_pstock):
    lang = request.param
    user, cash, purchased_stock, snapshot = get_download_data_of_pstock

    if lang == 'en':
      this_tz = 'UTC'
    elif lang == 'ja':
      this_tz = 'Asia/Tokyo'
    config = {
      'lang': lang,
      'timezone': this_tz,
      'user': user,
      'cash': cash,
      'pstock': purchased_stock,
      'snapshot': snapshot,
    }

    return config

  # ===============================
  # Download snapshot as CSV format
  # ===============================
  def test_check_download_snapshot_for_csv_format(self, settings, mocker, get_test_data_of_download_snapshot, csrf_exempt_django_app):
    config = get_test_data_of_download_snapshot
    settings.TIME_ZONE = config['timezone']
    mocker.patch('stock.models.get_language', return_value=config['lang'])
    # Create expected data
    pstock = config['pstock']
    cash = models._SnapshotRecord(
      code='-',
      price=0.0,
      dividend=0.0,
      per=0.0,
      pbr=0.0,
      eps=0.0,
      bps=0.0,
      roe=0.0,
      er=0.0,
      name=str(gettext_lazy('Cash')),
      industry='-',
      trend='-',
      purchased_value=config['cash'].balance,
    )
    instance = models._SnapshotRecord(
      code=pstock.stock.code,
      price=float(pstock.stock.price),
      dividend=float(pstock.stock.dividend),
      per=float(pstock.stock.per),
      pbr=float(pstock.stock.pbr),
      eps=float(pstock.stock.eps),
      bps=float(pstock.stock.bps),
      roe=float(pstock.stock.roe),
      er=float(pstock.stock.er),
    )
    instance.name = pstock.stock.get_name()
    instance.industry = pstock.stock.industry.get_name()
    instance.trend = str(instance._get_trend(pstock.stock.industry.is_defensive))
    instance.add_count(pstock.count)
    instance.add_value(float(pstock.price), pstock.count)
    lines = '\n'.join([
      ','.join([str(val) for val in instance.get_header()]),
      ','.join(cash.get_record()),
      ','.join(instance.get_record()) + '\n',
    ])
    expected = {
      'data': bytes(lines, 'utf-8'),
      'filename': 'snapshot-{}.csv'.format(config['snapshot']._replace_title()),
    }
    #
    # Execution
    #
    app = csrf_exempt_django_app
    page = app.get(self.snapshot_list_url, user=config['user'])
    target_url = self.snapshot_download_csv_url(config['snapshot'].pk)
    response = page.click(href=target_url)
    # Collect results
    attachment = response['content-disposition']
    stream = response.content

    assert expected['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert expected['data'] in stream

  # ================================
  # Download snapshot as JSOM format
  # ================================
  def test_check_download_snapshot_for_json_format(self, settings, mocker, get_download_data_of_pstock, csrf_exempt_django_app):
    mocker.patch('stock.models.get_language', return_value='en')
    user, _, _, snapshot = get_download_data_of_pstock
    # Create expected data
    data = {
      'title': snapshot.title,
      'detail': json.loads(snapshot.detail),
      'priority': snapshot.priority,
      'start_date': models.convert_timezone(snapshot.start_date, is_string=True),
      'end_date': models.convert_timezone(snapshot.end_date, is_string=True),
    }
    text_record = json.dumps(data, ensure_ascii=False, indent=2)
    expected = {
      'data': bytes(text_record, 'utf-8'),
      'filename': 'snapshot-{}.json'.format(snapshot._replace_title()),
    }
    #
    # Execution
    #
    app = csrf_exempt_django_app
    page = app.get(self.snapshot_list_url, user=user)
    target_url = self.snapshot_download_json_url(snapshot.pk)
    response = page.click(href=target_url)
    # Collect results
    attachment = response['content-disposition']
    output = response.content

    assert expected['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert expected['data'] in output

  # =============
  # Invalid cases
  # =============
  # Download process
  @pytest.mark.parametrize([
    'target_link',
  ], [
    ('snapshot_download_csv_url', ),
    ('snapshot_download_json_url', ),
  ], ids=['download-other-user-csv-file', 'download-other-user-json-file'])
  def test_invalid_download_request_for_each_format(self, init_webtest, target_link):
    app, users = init_webtest
    owner = users['owner']
    other = users['other']
    snapshot = factories.SnapshotFactory(user=owner)
    # Invalid request for snapshot download
    with pytest.raises(AppError) as ex:
      get_link = getattr(self, target_link)
      app.get(get_link(snapshot.pk), user=other)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  # ============
  # Stock search
  # ============
  @pytest.mark.parametrize([
    'condition',
    'ordering',
    'count',
    'exacts',
  ], [
    ('name == "skipped"', '-price', 0, []),
    ('name == "sample"', '-price', 1, ['sample']),
    ('name in "hoge"', '-price', 2, ['hogehoge', 'hoge-foo']),
    ('1000 < price < 1200 and industry_name == "alpha"', '-price', 3, ['hogehoge', 'hoge-foo', 'bar']),
    ('', 'price', 150, ['stock']),
  ], ids=[
    'target-does-not-exist',
    'there-is-only-one-target',
    'there-are-two-targets',
    'there-are-three-targets',
    'there-are-targets-which-can-show-in-a-page',
  ])
  def test_search_stock_by_using_form(self, mocker, get_sample_data_for_stock_search, init_webtest, condition, ordering, count, exacts):
    mocker.patch('stock.models.get_language', return_value='en')
    app, users = init_webtest
    owner = users['owner']
    all_stocks = get_sample_data_for_stock_search
    all_queryset = models.Stock.objects.filter(pk__in=self.get_pks(all_stocks))
    mocker.patch('stock.models.Stock.objects.get_queryset', return_value=all_queryset)

    # Execution
    forms = app.get(self.list_stock_url, user=owner).forms
    form = forms['stock-search-form']
    form['condition'] = condition
    form['ordering'] = ordering
    response = form.submit()
    # Collect response data
    records = response.context['stocks']
    elements = [
      element.contents[0] for element in response.html.find_all('td', attrs={'data-type': 'name'})
    ]

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.list_stock_url
    assert len(records) == count
    assert all([elem.startswith(tuple(exacts)) for elem in elements])

  # ===============
  # Download stocks
  # ===============
  @pytest.mark.parametrize([
    'params',
    'exact_fname',
    'indices',
  ], [
    ({'filename': 'foo', 'condition': 'price < 1200', 'ordering': 'roe,-price'}, 'stock-foo.csv', [0, 4, 1, 2]),
    ({'filename': 'hogehoge.csv', 'condition': 'price < 1200', 'ordering': 'roe,-price'}, 'stock-hogehoge.csv', [0, 4, 1, 2]),
    ({'filename': '.csv', 'condition': 'price < 1200', 'ordering': 'roe,-price'}, 'stock-20010105-080107.csv', [0, 4, 1, 2]),
    ({'filename': 'foo', 'condition': '', 'ordering': '-code'}, 'stock-foo.csv', [4, 3, 2, 1, 0]),
    ({'filename': 'foo', 'condition': 'price < 1200', 'ordering': ''}, 'stock-foo.csv', [0, 1, 2, 4]),
  ], ids=[
    'normal-filename',
    'filename-with-extension',
    'only-extension',
    'no-condition',
    'no-ordering',
  ])
  def test_download_filtered_stock_by_csv_format(self, mocker, get_sample_data_for_stock_search, init_webtest, params, exact_fname, indices):
    all_stocks = get_sample_data_for_stock_search
    all_queryset = models.Stock.objects.get_queryset().filter(pk__in=self.get_pks(all_stocks))
    mocker.patch('stock.models.get_language', return_value='en')
    mocker.patch('stock.models.generate_default_filename', return_value='20010105-080107')
    mocker.patch('stock.models.Stock.objects.get_queryset', return_value=all_queryset)
    # Create expected values
    rows = []
    for idx in indices:
      obj = all_stocks[idx]
      div_yield = obj.dividend / obj.price * Decimal('100.0')
      multi_pp = obj.per * obj.pbr
      # Add data
      rows.append([
        obj.code, obj.get_name(), str(obj.industry), str(obj.price), str(obj.dividend),
        f'{div_yield:.2f}', str(obj.per), str(obj.pbr), f'{multi_pp:.2f}',
        str(obj.eps), str(obj.bps), str(obj.roe), str(obj.er),
      ])
    header = ','.join([
      'Stock code', 'Stock name', 'Stock industry', 'Stock price', 'Dividend', 'Dividend yield',
      'Price Earnings Ratio (PER)', 'Price Book-value Ratio (PBR)', 'PER x PBR', 'Earnings Per Share (EPS)',
      'Book value Per Share (BPS)', 'Return On Equity (ROE)', 'Equity Ratio (ER)',
    ])
    lines = '\n'.join([','.join(record) for record in rows]) + '\n'
    expected = {
      'data': bytes(f'{header}\n' + lines, 'utf-8'),
      'filename': exact_fname,
    }
    #
    # Execute process
    #
    app, users = init_webtest
    forms = app.get(self.list_stock_url, user=users['owner']).forms
    form = forms['download-stock-form']
    for key, val in params.items():
      form[key] = val
    # Send post request
    response = form.submit()
    cookie = response.client.cookies.get('stock_download_status')
    attachment = response['content-disposition']
    stream = response.content
    #
    # Check stream data
    #
    def check_stream_data(recieved_stream, exact_stream):
      # Decode recieved stream as 'utf-8-sig' because of using BOM
      estimated_reader = csv.DictReader(StringIO(recieved_stream.decode('utf-8-sig')), delimiter=',')
      exact_reader = csv.DictReader(StringIO(exact_stream.decode('utf-8')), delimiter=',')
      results = []

      for recv, exact in zip(estimated_reader, exact_reader):
        outs = []

        for key in exact.keys():
          if key in ['Stock code', 'Stock name', 'Stock industry']:
            outs += [recv[key] == exact[key]]
          else:
            # Because the number of significant digits is up to two decimal places (LSB: 0.01),
            # an error of two decimal places is allowed.
            outs += [abs(float(recv[key]) - float(exact[key])) < 0.015]
        results += [all(outs)]

      return results

    assert expected['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert cookie.value == 'completed'
    assert check_stream_data(stream, expected['data'])

  @pytest.mark.parametrize([
    'params',
    'expected_cond',
    'expected_order',
  ], [
    ({'filename': '1'*129, 'condition': 'price > 100', 'ordering': 'code'}, 'price > 100', 'code'),
    ({'filename': 'hoge', 'condition': '1'*1025, 'ordering': 'code'}, '', 'code'),
    ({'filename': 'hoge', 'condition': 'price > 100', 'ordering': '1'*1025}, 'price > 100', ''),
  ], ids=[
    'too-long-filename',
    'too-long-condition',
    'too-long-ordering',
  ])
  def test_invalid_request_for_download_stock_form(self, init_webtest, params, expected_cond, expected_order):
    query_string = urllib.parse.quote('condition={}&ordering={}'.format(expected_cond, expected_order))
    location = '{}?{}'.format(self.list_stock_url, query_string)
    #
    # Execute process
    #
    app, users = init_webtest
    forms = app.get(self.list_stock_url, user=users['owner']).forms
    form = forms['download-stock-form']
    # Set form parameters
    for key, val in params.items():
      form[key] = val
    # Send post request
    response = form.submit()

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == location

# ============================
# Check a series of processing
# ============================
@pytest.mark.webtest
@pytest.mark.django_db
class TestWholeTimeSeriesProcessing(BaseStockTestUtils):
  def test_check_a_seires_of_processing(self, settings, csrf_exempt_django_app):
    settings.TIME_ZONE = 'Asia/Tokyo'
    app = csrf_exempt_django_app
    user_params = {
      'username': 'test',
      'email': 'test@user.com',
      'password': 'user-pass',
      'screen_name': 'sample-user',
    }
    user = UserModel.objects.create_user(**user_params)
    industries = factories.IndustryFactory.create_batch(16)
    for industry in industries:
      _ = factories.LocalizedIndustryFactory(language_code='en', industry=industry)
      _ = factories.LocalizedIndustryFactory(language_code='ja', industry=industry)
    # Create stocks by using each industry
    for industry in industries:
      stocks = factories.StockFactory.create_batch(8, industry=industry)

      for stock in stocks:
        _ = factories.LocalizedStockFactory(language_code='en', stock=stock)
        _ = factories.LocalizedStockFactory(language_code='ja', stock=stock)
    status_codes = []
    results = []

    # Step1: login
    form = app.get(self.login_url).forms['login-form']
    form['username'] = user_params['username']
    form['password'] = user_params['password']
    res = form.submit().follow()
    status_codes.append(res.status_code)
    next_link = get_current_path(res)
    # Step2: Access to Cash list page and register cashes
    res = app.get(next_link).click('Cash list')
    status_codes.append(res.status_code)
    next_link = get_current_path(res)
    options = [
      {'balance':  750000, 'registered_date': '2020-12-11'},
      {'balance':  750000, 'registered_date':  '2021-1-1' }, # From 2021/1/1
      {'balance':  122788, 'registered_date':  '2021-9-10'}, #                to 2021/9/10
      {'balance': 1000000, 'registered_date': '2021-12-4' }, # From 2021/12/4
      {'balance':   77516, 'registered_date':  '2022-2-2' }, #                to 2022/2/2
    ]
    # Execute form process
    for params in options:
      res = app.get(next_link).click('Register cash')
      status_codes.append(res.status_code)
      next_link = get_current_path(res)
      form = app.get(next_link).forms['cash-form']
      for key, val in params.items():
        form[key] = val
      res = form.submit().follow()
      status_codes.append(res.status_code)
      next_link = get_current_path(res)
    page = app.get(next_link)
    status_codes.append(page.status_code)
    results.append(len(page.context['cashes']) == len(options))
    res = page.click('Home')
    status_codes.append(res.status_code)
    next_link = get_current_path(res)

    # Step3: Access to Purchased-stock list page and register purchased-stocks
    res = app.get(next_link).click('Purchased stock list')
    status_codes.append(res.status_code)
    next_link = get_current_path(res)
    options = [
      # From 2021/1/1 to 2021/9/10
      {'stock':stocks[0].pk,'price':Decimal('1001.10'),'purchase_date':'2021-03-13','count':100}, # 100,110
      {'stock':stocks[1].pk,'price':Decimal(  '99.90'),'purchase_date': '2021-04-1','count':200}, #  19,980
      {'stock':stocks[2].pk,'price':Decimal('1010.50'),'purchase_date': '2021-4-28','count':100}, # 101,050
      {'stock':stocks[1].pk,'price':Decimal( '121.00'),'purchase_date': '2021-5-11','count':100}, #  12,100
      {'stock':stocks[2].pk,'price':Decimal('1111.50'),'purchase_date': '2021-6-09','count':200}, # 222,300
      {'stock':stocks[3].pk,'price':Decimal( '296.71'),'purchase_date': '2021-8-11','count':200}, # 135.118
      {'stock':stocks[2].pk,'price':Decimal('1123.30'),'purchase_date':'2021-09-02','count':100}, # 112,330
      # Ignore the following record (2021/10/11) when snapshot is created
      {'stock':stocks[4].pk,'price':Decimal('3030.11'),'purchase_date':'2021-10-11','count':100}, # 303,011
      # From 2021/12/4 to 2022/2/2
      {'stock':stocks[4].pk,'price':Decimal('4801.00'),'purchase_date':'2021-12-10','count':100}, # 480,100
      {'stock':stocks[0].pk,'price':Decimal( '990.70'),'purchase_date': '2022-01-5','count':200}, # 198,140
      {'stock':stocks[1].pk,'price':Decimal( '130.59'),'purchase_date':'2022-01-20','count':200}, #  26,118
      {'stock':stocks[3].pk,'price':Decimal( '360.13'),'purchase_date': '2022-1-25','count':300}, # 108,039
      {'stock':stocks[2].pk,'price':Decimal('1100.88'),'purchase_date': '2022-1-28','count':100}, # 110,088
    ]
    # Execute form process
    for params in options:
      res = app.get(next_link).click('Register purchased stock')
      status_codes.append(res.status_code)
      next_link = get_current_path(res)
      form = app.get(next_link).forms['purchased-stock-form']
      for key, val in params.items():
        form[key] = val
      res = form.submit().follow()
      status_codes.append(res.status_code)
      next_link = get_current_path(res)
    page = app.get(next_link)
    status_codes.append(page.status_code)
    # Check total records
    total_pstocks = len(page.context['pstocks'])
    results.append(total_pstocks == len(options))
    res = page.click('Home')
    status_codes.append(res.status_code)
    next_link = get_current_path(res)

    # Step4: Access to Snapshot list page and register snapshots
    res = app.get(next_link).click('Snapshot list')
    status_codes.append(res.status_code)
    next_link = get_current_path(res)
    options = [
      {'title':'Until 2020/12/31',                                       'end_date':'2020-12-31'},
      {'title':'From  2021/1/1 to 2021/9/10', 'start_date':'2021-01-01', 'end_date': '2021-9-11'},
      {'title':'From 2021/12/4 to 2022/2/2',  'start_date':'2021-12-04', 'end_date': '2022-2-2'},
    ]
    # Execute form process
    for params in options:
      res = app.get(next_link).click('Register snapshot')
      status_codes.append(res.status_code)
      next_link = get_current_path(res)
      form = app.get(next_link).forms['snapshot-form']
      for key, val in params.items():
        form[key] = val
      res = form.submit().follow()
      status_codes.append(res.status_code)
      next_link = get_current_path(res)
    page = app.get(next_link)
    status_codes.append(page.status_code)
    snapshots = page.context['snapshots']
    results.append(len(snapshots) == len(options))
    res = page.click('Home')
    status_codes.append(res.status_code)
    next_link = get_current_path(res)

    # Step5: Access to dashboard page
    res = app.get(next_link).click('Dashboard')
    status_codes.append(res.status_code)
    next_link = get_current_path(res)
    details = []
    # Collect detail of snapshots (ordering: '-end_date')
    for ss in snapshots:
      element = res.html.find('script', id=str(ss.uuid))
      details.append(json.loads(element.contents[0]))
    page = app.get(next_link)
    res = page.click('Home')
    status_codes.append(res.status_code)
    next_link = get_current_path(res)

    # Step6: Access to history page
    res = app.get(next_link).click('Investment history')
    status_codes.append(res.status_code)
    histories = []
    # Collect histories of snapshots (ordering: '-end_date')
    for ss in snapshots:
      uuid = str(ss.uuid)
      element = res.html.find('script', id=uuid)
      histories.append(json.loads(element.contents[0]))

    # --------------
    # Assert process
    # --------------
    calc_pstock_sum = lambda ps_records: sum([target['price'] * target['count'] for target in ps_records])
    chk_ss = lambda callback: all([callback(target) for target in [details, histories]])
    # Check status_codes and results
    assert all([_status_code == status.HTTP_200_OK for _status_code in status_codes])
    assert all(results)
    # Check cashes
    assert chk_ss(lambda target: target[2]['cash']['balance'] == 750000)
    assert chk_ss(lambda target: target[2]['cash']['registered_date'] == '2020-12-11T00:00:00+09:00')
    assert chk_ss(lambda target: target[1]['cash']['balance'] == 122788)
    assert chk_ss(lambda target: target[1]['cash']['registered_date'] == '2021-09-10T00:00:00+09:00')
    assert chk_ss(lambda target: target[0]['cash']['balance'] == 77516)
    assert chk_ss(lambda target: target[0]['cash']['registered_date'] == '2022-02-02T00:00:00+09:00')
    # Check purchased stock
    assert chk_ss(lambda target: calc_pstock_sum(target[2]['purchased_stocks']) == 0)
    assert chk_ss(lambda target: calc_pstock_sum(target[1]['purchased_stocks']) == 627212)
    assert chk_ss(lambda target: calc_pstock_sum(target[0]['purchased_stocks']) == 922485)