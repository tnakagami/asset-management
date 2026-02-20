import pytest
import json
import urllib.parse
from pytest_django.asserts import assertTemplateUsed, assertQuerySetEqual
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError
from django.urls import reverse
from urllib.parse import urlencode
from app_tests import (
  status,
  factories,
  get_date,
  BaseTestUtils,
)
from stock import models

@pytest.fixture(scope='module')
def get_stock_records(django_db_blocker):
  with django_db_blocker.unblock():
    stocks = [
      factories.StockFactory(code='0001'),
      factories.StockFactory(code='0002'),
      factories.StockFactory(code='0003'),
      factories.StockFactory(code='0004'),
      factories.StockFactory(code='0005'),
      factories.StockFactory(code='0006'),
    ]
    localized_stocks = [
      factories.LocalizedStockFactory(name='stock01', language_code='en', stock=stocks[0]),
      factories.LocalizedStockFactory(name='stock02', language_code='en', stock=stocks[1]),
      factories.LocalizedStockFactory(name='stock03', language_code='en', stock=stocks[2]),
      factories.LocalizedStockFactory(name='stock04', language_code='en', stock=stocks[3]),
      factories.LocalizedStockFactory(name='stock05', language_code='en', stock=stocks[4]),
      factories.LocalizedStockFactory(name='stock06', language_code='en', stock=stocks[5]),
    ]

  return stocks

class SharedFixture(BaseTestUtils):
  login_url = reverse('account:login')

  def compare_form_data(self, instance, form_data=None, other=None):
    results = []
    # Get form data
    if form_data is None:
      form_data = self.form_data

    for key, val in form_data.items():
      if key != 'stock':
        results += [getattr(instance, key) == getattr(other, key, val)]
      else:
        stock = getattr(other, 'stock', None)
        results += [instance.stock.pk == getattr(stock, 'pk', val)]
    out = all(results)

    return out

  @pytest.fixture
  def login_process(self, client, get_user):
    def inner(user=None):
      if user is None:
        user = get_user
      client.force_login(user)

      return client, user

    return inner

  @pytest.fixture(scope='class')
  def get_specific_user(self, django_db_blocker):
    with django_db_blocker.unblock():
      user = factories.UserFactory()

    return user

  @pytest.fixture
  def wrap_login(self, login_process, get_specific_user):
    client, user = login_process(user=get_specific_user)

    return client, user

# =========
# Dashboard
# =========
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
class TestDashboard(SharedFixture):
  dashboard_url = reverse('stock:dashboard')

  def test_get_access_by_logged_in_user(self, login_process):
    client, _ = login_process()
    response = client.get(self.dashboard_url)

    assert response.status_code == status.HTTP_200_OK

  def test_get_access_without_authentication(self, client):
    url = self.dashboard_url
    response = client.get(url)
    expected = '{}?next={}'.format(self.login_url, url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == expected

# =================
# InvestmentHistory
# =================
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
class TestInvestmentHistory(SharedFixture):
  history_url = reverse('stock:investment_history')

  def test_get_access_by_logged_in_user(self, login_process):
    client, _ = login_process()
    response = client.get(self.history_url)

    assert response.status_code == status.HTTP_200_OK

  def test_get_access_without_authentication_for_history_page(self, client):
    url = self.history_url
    response = client.get(url)
    expected = '{}?next={}'.format(self.login_url, url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == expected

# =================
# StockAjaxResponse
# =================
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
class TestStockAjaxResponse(SharedFixture):
  stock_ajax_url = reverse('stock:ajax_stock')

  def test_get_access_by_logged_in_user(self, client, mocker, get_stock_records):
    stocks = get_stock_records
    queryset = models.Stock.objects.filter(pk__in=self.get_pks(stocks))
    qs_mock = mocker.patch('stock.models.StockManager.get_queryset', return_value=queryset)
    mocker.patch('stock.models.get_language', return_value='en')
    response = client.get(self.stock_ajax_url)
    content = json.loads(response.content)
    data = content['qs']
    keys = ['pk', 'name', 'code']
    exact_qs = queryset.select_targets()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(data, list)
    assert all([
      all([key in item.keys() for key in keys]) for item in data
    ])
    assert len(exact_qs) == len(data)
    assert all([
      all([getattr(_stock, key) == item[key] for key in keys])
      for _stock, item in zip(exact_qs, data)
    ])
    assert qs_mock.call_count == 1

  def test_post_invalid_access(self, client):
    response = client.post(self.stock_ajax_url)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

# =========
# CashViews
# =========
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
class TestCashViews(SharedFixture):
  list_url = reverse('stock:list_cash')
  create_url = reverse('stock:register_cash')
  update_url = lambda _self, pk: reverse('stock:update_cash', kwargs={'pk': pk})
  delete_url = lambda _self, pk: reverse('stock:delete_cash', kwargs={'pk': pk})
  form_data = {
    'balance': 12345,
    'registered_date': get_date((2020, 10, 12)),
  }

  # ========
  # ListView
  # ========
  def test_access_to_listview(self, wrap_login):
    client, _ = wrap_login
    response = client.get(self.list_url)

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_listview_without_authentication(self, client):
    url = self.list_url
    response = client.get(url)
    expected = '{}?next={}'.format(self.login_url, url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == expected

  # ==========
  # CreateView
  # ==========
  def test_access_to_createview(self, wrap_login):
    client, _ = wrap_login
    response = client.get(self.create_url)

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_createvie_without_authentication(self, client):
    response = client.get(self.create_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_createview(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    response = client.post(self.create_url, data=self.form_data)
    total = models.Cash.objects.filter(user=user).count()

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert total == 1

  # ==========
  # UpdateView
  # ==========
  def test_access_to_updateview(self, wrap_login):
    client, user = wrap_login
    instance = factories.CashFactory(user=user)
    response = client.get(self.update_url(instance.pk))

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_updateview_without_authentication(self, client):
    instance = factories.CashFactory()
    response = client.get(self.update_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_invalid_access_to_updateview(self, wrap_login):
    client, _ = wrap_login
    instance = factories.CashFactory()
    response = client.get(self.update_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_updateview(self, wrap_login):
    client, user = wrap_login
    target = factories.CashFactory(user=user)
    response = client.post(
      self.update_url(target.pk),
      data=urlencode(self.form_data),
      content_type='application/x-www-form-urlencoded',
    )
    instance = models.Cash.objects.get(pk=target.pk)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert self.compare_form_data(instance)

  def test_invalid_post_access_to_updateview(self, wrap_login):
    client, _ = wrap_login
    target = factories.CashFactory()
    response = client.post(
      self.update_url(target.pk),
      data=urlencode(self.form_data),
      content_type='application/x-www-form-urlencoded',
    )
    instance = models.Cash.objects.get(pk=target.pk)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert self.compare_form_data(instance, other=target)

  # ==========
  # DeleteView
  # ==========
  def test_access_to_deleteview(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    instance = factories.CashFactory(user=user)
    response = client.get(self.delete_url(instance.pk))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  def test_access_to_deleteview_without_authentication(self, client):
    instance = factories.CashFactory()
    response = client.get(self.delete_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_deleteview(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    target = factories.CashFactory(user=user)
    response = client.post(self.delete_url(target.pk))
    total = models.Cash.objects.filter(user=user).count()

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert total == 0

  def test_invalid_post_access_to_deleteview(self, wrap_login):
    client, _ = wrap_login
    target = factories.CashFactory()
    response = client.post(self.delete_url(target.pk))
    total = models.Cash.objects.filter(pk=target.pk).count()

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert total == 1

# ===================
# PurchasedStockViews
# ===================
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
class TestPurchasedStockViews(SharedFixture):
  list_url = reverse('stock:list_purchased_stock')
  create_url = reverse('stock:register_purchased_stock')
  update_url = lambda _self, pk: reverse('stock:update_purchased_stock', kwargs={'pk': pk})
  delete_url = lambda _self, pk: reverse('stock:delete_purchased_stock', kwargs={'pk': pk})
  upload_url = reverse('stock:upload_purchased_stock')

  @property
  def form_data(self):
    stock = factories.StockFactory()
    params = {
      'stock': stock.pk,
      'price': 5678,
      'purchase_date': get_date((2022, 3, 7)),
      'count': 120,
      'has_been_sold': False,
    }

    return params

  # ========
  # ListView
  # ========
  def test_access_to_listview(self, wrap_login):
    client, _ = wrap_login
    response = client.get(self.list_url)

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_listview_without_authentication(self, client):
    url = self.list_url
    response = client.get(url)
    expected = '{}?next={}'.format(self.login_url, url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == expected

  @pytest.fixture(scope='class')
  def get_pseudo_purchased_stocks(self, django_db_blocker, get_stock_records):
    with django_db_blocker.unblock():
      user = factories.UserFactory()
      stocks = get_stock_records
      purchased_stocks = [
        factories.PurchasedStockFactory(user=user, stock=stocks[0], price=500,  purchase_date=get_date((2010, 1, 1))),
        factories.PurchasedStockFactory(user=user, stock=stocks[2], price=1000, purchase_date=get_date((2017, 1, 1))),
        factories.PurchasedStockFactory(user=user, stock=stocks[5], price=1500, purchase_date=get_date((2017, 1, 2))),
        factories.PurchasedStockFactory(user=user, stock=stocks[3], price=1400, purchase_date=get_date((2018, 1, 1))),
        factories.PurchasedStockFactory(user=user, stock=stocks[3], price=1200, purchase_date=get_date((2017, 1, 2))),
      ]

    return user, purchased_stocks

  @pytest.mark.parametrize([
    'query_params',
    'indices',
  ], [
    ({'condition': 'price >= 1000'}, [3, 4, 2, 1]),
    ({'condition': '10 < 100'}, [3, 4, 2, 1, 0]),
    ({}, [3, 4, 2, 1, 0]),
  ], ids=[
    'with-valid-condition',
    'with-invalid-condition',
    'without-condition',
  ])
  def test_access_with_query(self, login_process, get_pseudo_purchased_stocks, query_params, indices):
    user, purchased_stocks = get_pseudo_purchased_stocks
    client, user = login_process(user=user)
    response = client.get(self.list_url, query_params=query_params)
    exact_qs = models.PurchasedStock.objects.filter(pk__in=self.get_pks([purchased_stocks[idx] for idx in indices]))

    assert response.status_code == status.HTTP_200_OK
    assert response.context['form'] is not None
    assert response.context['pstocks'].count() == exact_qs.count()
    assertQuerySetEqual(response.context['pstocks'], exact_qs, ordered=True)

  # ==========
  # CreateView
  # ==========
  def test_access_to_createview(self, wrap_login):
    client, _ = wrap_login
    response = client.get(self.create_url)

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_createvie_without_authentication(self, client):
    response = client.get(self.create_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_createview(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    response = client.post(self.create_url, data=self.form_data)
    total = models.PurchasedStock.objects.filter(user=user).count()

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert total == 1

  # ==========
  # UpdateView
  # ==========
  def test_access_to_updateview(self, wrap_login):
    client, user = wrap_login
    instance = factories.PurchasedStockFactory(user=user)
    response = client.get(self.update_url(instance.pk))

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_updateview_without_authentication(self, client):
    instance = factories.PurchasedStockFactory()
    response = client.get(self.update_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_invalid_access_to_updateview(self, wrap_login):
    client, _ = wrap_login
    instance = factories.PurchasedStockFactory()
    response = client.get(self.update_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_updateview(self, wrap_login):
    client, user = wrap_login
    target = factories.PurchasedStockFactory(user=user)
    form_data = self.form_data
    response = client.post(
      self.update_url(target.pk),
      data=urlencode(form_data),
      content_type='application/x-www-form-urlencoded',
    )
    instance = models.PurchasedStock.objects.get(pk=target.pk)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert self.compare_form_data(instance, form_data=form_data)

  def test_invalid_post_access_to_updateview(self, wrap_login):
    client, _ = wrap_login
    target = factories.PurchasedStockFactory()
    form_data = self.form_data
    response = client.post(
      self.update_url(target.pk),
      data=urlencode(form_data),
      content_type='application/x-www-form-urlencoded',
    )
    instance = models.PurchasedStock.objects.get(pk=target.pk)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert self.compare_form_data(instance, form_data=form_data, other=target)

  # ==========
  # DeleteView
  # ==========
  def test_access_to_deleteview(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    instance = factories.PurchasedStockFactory(user=user)
    response = client.get(self.delete_url(instance.pk))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  def test_access_to_deleteview_without_authentication(self, client):
    instance = factories.PurchasedStockFactory()
    response = client.get(self.delete_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_deleteview(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    target = factories.PurchasedStockFactory(user=user)
    response = client.post(self.delete_url(target.pk))
    total = models.PurchasedStock.objects.filter(user=user).count()

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert total == 0

  def test_invalid_post_access_to_deleteview(self, wrap_login):
    client, _ = wrap_login
    target = factories.PurchasedStockFactory()
    response = client.post(self.delete_url(target.pk))
    total = models.PurchasedStock.objects.filter(pk=target.pk).count()

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert total == 1

  # ==========
  # UploadView
  # ==========
  def test_access_to_uploadview(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    response = client.get(self.upload_url)

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_uploadview_without_authentication(self, client):
    url = self.upload_url
    response = client.get(url)
    expected = '{}?next={}'.format(self.login_url, url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == expected

  def test_valid_post_access_to_uploadview(self, mocker, get_stock_records, login_process, get_csvfile_form_param):
    stocks = get_stock_records
    params, files = get_csvfile_form_param
    data = {
      'encoding': params['encoding'],
      'header': params['header'],
      'csv_file': files['csv_file'],
    }
    csv_data = [
      [stocks[0].code, '2021-01-02',       '1200',     '50'],
      [stocks[1].code, '2024-01-2',        '1001.12', '100'],
      [stocks[2].code, '1990-03-02 00:12', '1031.0',  '200'],
    ]
    expected = [
      (stocks[0].code, '2021-01-02T00:00:00+00:00', 1200.00,  50),
      (stocks[1].code, '2024-01-02T00:00:00+00:00', 1001.12, 100),
      (stocks[2].code, '1990-03-02T00:00:00+00:00', 1031.00, 200),
    ]
    mocker.patch('stock.forms.UploadPurchasedStockForm.filtering', side_effect=csv_data)
    # Send request
    client, user = login_process(user=factories.UserFactory())
    response = client.post(self.upload_url, data=data)
    pstocks = user.purchased_stocks.all()
    p1 = pstocks.get(stock__code=expected[0][0])
    p2 = pstocks.get(stock__code=expected[1][0])
    p3 = pstocks.get(stock__code=expected[2][0])
    # Define checker
    def checker(obj, exacts):
      valid_date = models.convert_timezone(obj.purchase_date, is_string=True) == exacts[1]
      valid_price = abs(float(obj.price) - exacts[2]) < 1e-2
      valid_count = obj.count == exacts[3]
      out = all([valid_date, valid_price, valid_count])

      return out

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert len(pstocks) == len(expected)
    assert checker(p1, expected[0])
    assert checker(p2, expected[1])
    assert checker(p3, expected[2])

  @pytest.fixture(params=[
    'form-invalid',
    'invalid-bulk-create-with-integrity-err',
    'unexpected-error-occurred',
    'invalid-header-input',
  ])
  def invalid_form_data_in_uploadview(self, request, mocker, get_single_csvfile_form_data):
    has_header = True
    err_msg = ''
    key = request.param

    if key == 'form-invalid':
      mocker.patch('stock.forms.UploadPurchasedStockForm.clean', side_effect=ValidationError('invalid-inputs'))
      err_msg = 'invalid-inputs'
    elif key == 'invalid-bulk-create-with-integrity-err':
      mocker.patch('stock.forms.UploadPurchasedStockForm.clean', return_value=None)
      mocker.patch('stock.forms.UploadPurchasedStockForm.get_data', return_value=[])
      mocker.patch('stock.models.PurchasedStock.objects.bulk_create', side_effect=IntegrityError('invalid'))
      err_msg = 'Include invalid records. Please check the detail: invalid.'
    elif key == 'unexpected-error-occurred':
      mocker.patch('stock.forms.UploadPurchasedStockForm.clean', return_value=None)
      mocker.patch('stock.forms.UploadPurchasedStockForm.get_data', side_effect=Exception('Err'))
      err_msg = 'Unexpected error occurred: Err.'
    elif key == 'invalid-header-input':
      has_header = False
      err_msg = 'Raise exception:'
    params, files = get_single_csvfile_form_data
    data = {
      'encoding': params['encoding'],
      'header': has_header,
      'csv_file': files['csv_file'],
    }

    return data, err_msg

  def test_invalid_request_in_uploadview(self, login_process, invalid_form_data_in_uploadview):
    client, user = login_process(user=factories.UserFactory())
    data, err_msg = invalid_form_data_in_uploadview
    # Send request
    response = client.post(self.upload_url, data=data)
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

# =============
# SnapshotViews
# =============
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
class TestSnapshotViews(SharedFixture):
  list_url = reverse('stock:list_snapshot')
  create_url = reverse('stock:register_snapshot')
  update_url = lambda _self, pk: reverse('stock:update_snapshot', kwargs={'pk': pk})
  delete_url = lambda _self, pk: reverse('stock:delete_snapshot', kwargs={'pk': pk})
  ajax_url = reverse('stock:update_all_snapshots')
  detail_url = lambda _self, pk: reverse('stock:detail_snapshot', kwargs={'pk': pk})
  form_data = {
    'title': 'sample-snapshot',
    'start_date': get_date((2023, 4, 5)),
    'end_date':   get_date((2023, 7, 9)),
    'priority': 99,
  }

  # ========
  # ListView
  # ========
  def test_access_to_listview(self, wrap_login):
    client, _ = wrap_login
    response = client.get(self.list_url)

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_listview_without_authentication(self, client):
    url = self.list_url
    response = client.get(url)
    expected = '{}?next={}'.format(self.login_url, url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == expected

  # ==========
  # CreateView
  # ==========
  def test_access_to_createview(self, wrap_login):
    client, _ = wrap_login
    response = client.get(self.create_url)

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_createvie_without_authentication(self, client):
    response = client.get(self.create_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_createview(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    response = client.post(self.create_url, data=self.form_data)
    total = models.Snapshot.objects.filter(user=user).count()

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert total == 1

  # ==========
  # UpdateView
  # ==========
  def test_access_to_updateview(self, wrap_login):
    client, user = wrap_login
    instance = factories.SnapshotFactory(user=user)
    response = client.get(self.update_url(instance.pk))

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_updateview_without_authentication(self, client):
    instance = factories.SnapshotFactory()
    response = client.get(self.update_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_invalid_access_to_updateview(self, wrap_login):
    client, _ = wrap_login
    instance = factories.SnapshotFactory()
    response = client.get(self.update_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_updateview(self, wrap_login):
    client, user = wrap_login
    target = factories.SnapshotFactory(user=user)
    response = client.post(
      self.update_url(target.pk),
      data=urlencode(self.form_data),
      content_type='application/x-www-form-urlencoded',
    )
    instance = models.Snapshot.objects.get(pk=target.pk)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert self.compare_form_data(instance)

  def test_invalid_post_access_to_updateview(self, wrap_login):
    client, _ = wrap_login
    target = factories.SnapshotFactory()
    response = client.post(
      self.update_url(target.pk),
      data=urlencode(self.form_data),
      content_type='application/x-www-form-urlencoded',
    )
    instance = models.Snapshot.objects.get(pk=target.pk)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert self.compare_form_data(instance, other=target)

  # ==========
  # DeleteView
  # ==========
  def test_access_to_deleteview(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    instance = factories.SnapshotFactory(user=user)
    response = client.get(self.delete_url(instance.pk))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  def test_access_to_deleteview_without_authentication(self, client):
    instance = factories.SnapshotFactory()
    response = client.get(self.delete_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_deleteview(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    target = factories.SnapshotFactory(user=user)
    response = client.post(self.delete_url(target.pk))
    total = models.Snapshot.objects.filter(user=user).count()

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert total == 0

  def test_invalid_post_access_to_deleteview(self, wrap_login):
    client, _ = wrap_login
    target = factories.SnapshotFactory()
    response = client.post(self.delete_url(target.pk))
    total = models.Snapshot.objects.filter(pk=target.pk).count()

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert total == 1

  # ========
  # AjaxView
  # ========
  def test_access_to_ajaxview(self, client):
    response = client.get(self.ajax_url)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  def test_post_access_with_valid_response_to_ajaxview(self, client, mocker):
    _mock = mocker.patch('stock.models.Snapshot.save_all', return_value=None)
    response = client.post(self.ajax_url)
    data = json.loads(response.content)

    assert response.status_code == status.HTTP_200_OK
    assert 'status' in data.keys()
    assert data['status']
    assert _mock.call_count == 1

  def test_post_access_with_invalid_response_to_ajaxview(self, client, mocker):
    _mock = mocker.patch('stock.models.Snapshot.save_all', side_effect=Exception('Error'))
    response = client.post(self.ajax_url)
    data = json.loads(response.content)

    assert response.status_code == status.HTTP_200_OK
    assert 'status' in data.keys()
    assert not data['status']
    assert _mock.call_count == 1

  # ==========
  # DetailView
  # ==========
  def test_access_to_detailview_without_authentication(self, client):
    instance = factories.SnapshotFactory()
    response = client.get(self.detail_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_invalid_request_to_detailview(self, wrap_login):
    client, _ = wrap_login
    instance = factories.SnapshotFactory()
    response = client.get(self.detail_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_get_request_to_detailview(self, mocker, login_process):
    pstock = {
      'stock': {
        'code': 'A1CC',
        'names': {'en': 'en-bar', 'ge': 'ge-bar'},
        'industry': {
          'names': {'en': 'en-YYY', 'ge': 'ge-YYY'},
          'is_defensive': False,
        },
        'price':  900.00, 'dividend': 0, 'per': 0, 'pbr': 0,
        'eps': 0, 'bps': 0, 'roe': 0, 'er':  0,
      },
      'price': 1000.00,
      'count': 300,
    }
    data = json.dumps({
      'cash': {'balance': 1000},
      'purchased_stocks': [pstock],
    })
    # Setup
    client, user = login_process(user=factories.UserFactory())
    instance = factories.SnapshotFactory(user=user)
    instance.detail = data
    instance.save()
    response = client.get(self.detail_url(instance.pk))
    snapshot = response.context['snapshot']
    records = snapshot.create_records()

    assert response.status_code == status.HTTP_200_OK
    assert snapshot.pk == instance.pk
    assert len(records) == 2
    assert all([key in ['cash', 'A1CC'] for key in records.keys()])
    assert abs(records['cash'].purchased_value - 1000.00) < 1e-6
    assert abs(records['A1CC'].price - 900.00) < 1e-6
    assert abs(records['A1CC'].purchased_value - 1000.00*300) < 1e-6
    assert records['A1CC'].count == 300

# ===================
# UploadDownloadViews
# ===================
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
class TestUploadDownloadViews(SharedFixture):
  json_upload_url = reverse('stock:upload_jsonformat_snapshot')
  csv_download_url = lambda _self, pk: reverse('stock:download_csv_snapshot', kwargs={'pk': pk})
  json_download_url = lambda _self, pk: reverse('stock:download_json_snapshot', kwargs={'pk': pk})

  # ===========================
  # Upload JSON Format Snapshot
  # ===========================
  def test_access_to_upload_json_format_snapshot(self, wrap_login):
    client, user = wrap_login
    response = client.get(self.json_upload_url)

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_upload_json_format_snapshot_without_authentication(self, client):
    url = self.json_upload_url
    response = client.get(url)
    expected = '{}?next={}'.format(self.login_url, url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == expected

  def test_post_access_to_upload_json_format_snapshot_without_authentication(self, client):
    url = self.json_upload_url
    response = client.post(url)
    expected = '{}?next={}'.format(self.login_url, url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == expected

  def test_check_valid_post_access_in_upload_json_format_snapshot(self, settings, get_jsonfile_form_param, login_process):
    settings.TIME_ZONE = 'Asia/Tokyo'
    client, user = login_process(user=factories.UserFactory())
    kwargs, files = get_jsonfile_form_param
    params = {
      'encoding': kwargs['encoding'],
      'json_file': files['json_file'],
    }
    response = client.post(self.json_upload_url, data=params)
    instance = models.Snapshot.objects.get(user=user)
    detail = json.loads(instance.detail)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == reverse('stock:list_snapshot')
    assert instance is not None
    assert instance.start_date.isoformat(timespec='seconds') == '2018-12-31T15:00:00+00:00'
    assert instance.end_date.isoformat(timespec='seconds') == '5364-12-29T15:00:00+00:00'
    assert instance.priority == 99
    assert detail['cash']['balance'] == 123
    assert len(detail['purchased_stocks']) == 1
    assert detail['purchased_stocks'][0]['count'] == 100

  def test_check_invalid_post_access_in_upload_json_format_snapshot(self, get_err_form_param_with_jsonfile, login_process):
    client, _ = login_process()
    kwargs, files, err_msg = get_err_form_param_with_jsonfile
    params = {
      'encoding': kwargs['encoding'],
      'json_file': files['json_file'],
    }
    # Send request
    response = client.post(self.json_upload_url, data=params)
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

  # =====================
  # Download CSV Snapshot
  # =====================
  def test_access_to_download_csv_snapshot_without_authentication(self, client):
    instance = factories.SnapshotFactory()
    response = client.get(self.csv_download_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_invalid_request_to_download_csv_snapshot(self, wrap_login):
    client, _ = wrap_login
    instance = factories.SnapshotFactory()
    response = client.get(self.csv_download_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_post_access_in_download_csv_snapshot(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    instance = factories.SnapshotFactory(user=user)
    response = client.post(self.csv_download_url(instance.pk))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  def test_get_request_to_download_csv_snapshot(self, mocker, login_process):
    output = {
      'rows': [['hoge','foo'], ['bar', '123']],
      'header': ['Col1', 'Col2'],
      'filename': urllib.parse.unquote('snapshot-test.csv'),
    }
    expected = bytes('Col1,Col2\nhoge,foo\nbar,123\n', 'utf-8')
    mocker.patch('stock.models.Snapshot.create_response_kwargs', return_value=output)
    # Get access
    client, user = login_process(user=factories.UserFactory())
    instance = factories.SnapshotFactory(user=user)
    response = client.get(self.csv_download_url(instance.pk))
    attachment = response.get('content-disposition')
    stream = response.getvalue()

    assert response.has_header('content-disposition')
    assert output['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert expected in stream

  # ======================
  # Download JSON Snapshot
  # ======================
  def test_access_to_download_json_snapshot_without_authentication(self, client):
    instance = factories.SnapshotFactory()
    response = client.get(self.json_download_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_post_access_in_download_json_snapshot(self, login_process):
    client, user = login_process(user=factories.UserFactory())
    instance = factories.SnapshotFactory(user=user)
    response = client.post(self.json_download_url(instance.pk))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  def test_invalid_request_to_download_json_snapshot(self, wrap_login):
    client, _ = wrap_login
    instance = factories.SnapshotFactory()
    response = client.get(self.json_download_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_get_request_to_download_json_snapshot(self, mocker, login_process):
    output = {
      'data': {
        'title': 'test',
        'detail': {
          'cash': {},
          'purchased_stocks': [],
        },
        'priority': 9,
        'start_date': '2021-02-13',
        'end_date': '2021-03-13',
      },
      'filename': urllib.parse.unquote('snapshot-test.json'),
    }
    text = json.dumps(output['data'], indent=2)
    expected = bytes(text.encode('utf-8'))
    # Get access
    client, user = login_process(user=factories.UserFactory())
    instance = factories.SnapshotFactory(user=user)
    mocker.patch('stock.models.Snapshot.create_json_from_model', return_value=output)
    response = client.get(self.json_download_url(instance.pk))
    attachment = response.get('content-disposition')
    binary = response.getvalue()

    assert response.has_header('content-disposition')
    assert output['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert expected in binary

# ============================
# PeriodicTaskRorSnapshotViews
# ============================
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
class TestPeriodicTaskForSnapshotViews(SharedFixture):
  list_url = reverse('stock:list_snapshot_task')
  create_url = reverse('stock:register_snapshot_task')
  update_url = lambda _self, pk: reverse('stock:update_snapshot_task', kwargs={'pk': pk})
  delete_url = lambda _self, pk: reverse('stock:delete_snapshot_task', kwargs={'pk': pk})

  @property
  def form_data(self):
    form_data = {
      'snapshot': 0,
      'name': 'ss-task20230145',
      'enabled': True,
      'snapshot': None,
      'schedule_type': 'every-week',
      'config': json.dumps({'minute': 10, 'hour': 20, 'day_of_week': 3}),
    }

    return form_data

  @pytest.fixture(scope='class')
  def create_snapshots(self, django_db_blocker):
    with django_db_blocker.unblock():
      user = factories.UserFactory()
      _ = factories.CashFactory.create_batch(2, user=user)
      _ = factories.PurchasedStockFactory.create_batch(3, user=user)
      snapshot = factories.SnapshotFactory(user=user)
      # Other snapshot
      other = factories.UserFactory()
      _ = factories.CashFactory.create_batch(3, user=other)
      _ = factories.PurchasedStockFactory.create_batch(2, user=other)
      _ = factories.SnapshotFactory(user=other)

    return user, snapshot

  # ========
  # ListView
  # ========
  def test_access_to_listview(self, wrap_login):
    client, _ = wrap_login
    response = client.get(self.list_url)

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_listview_without_authentication(self, client):
    url = self.list_url
    response = client.get(url)
    expected = '{}?next={}'.format(self.login_url, url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == expected

  # ==========
  # CreateView
  # ==========
  def test_access_to_createview(self, wrap_login):
    client, _ = wrap_login
    response = client.get(self.create_url)

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_createvie_without_authentication(self, client):
    response = client.get(self.create_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_post_access_to_createview(self, login_process, create_snapshots):
    user, snapshot = create_snapshots
    client, user = login_process(user=user)
    form_data = self.form_data
    form_data['snapshot'] = snapshot.pk
    response = client.post(self.create_url, data=form_data)
    params = json.dumps({'user_pk': user.pk, 'snapshot_pk': snapshot.pk})[1:-1]
    total = models.PeriodicTask.objects.filter(kwargs__contains=params).count()

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert total == 1

  # ==========
  # UpdateView
  # ==========
  def test_access_to_updateview(self, login_process, create_snapshots):
    user, snapshot = create_snapshots
    client, user = login_process(user=user)
    instance = factories.PeriodicTaskFactory(kwargs=json.dumps({'user_pk': user.pk, 'snapshot_pk': snapshot.pk}))
    response = client.get(self.update_url(instance.pk))

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_updateview_without_authentication(self, client, create_snapshots):
    user, snapshot = create_snapshots
    instance = factories.PeriodicTaskFactory(kwargs=json.dumps({'user_pk': user.pk, 'snapshot_pk': snapshot.pk}))
    response = client.get(self.update_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_updateview(self, login_process, create_snapshots):
    user, snapshot = create_snapshots
    client, user = login_process(user=user)
    params = json.dumps({'user_pk': user.pk, 'snapshot_pk': snapshot.pk})
    target = factories.PeriodicTaskFactory(kwargs=params, enabled=False)
    form_data = self.form_data
    form_data['snapshot'] = snapshot.pk
    response = client.post(
      self.update_url(target.pk),
      data=urlencode(form_data),
      content_type='application/x-www-form-urlencoded',
    )
    instance = models.PeriodicTask.objects.get(pk=target.pk)
    total = models.PeriodicTask.objects.filter(kwargs__contains=params).count()
    config = json.loads(form_data['config'])

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert instance.name == form_data['name']
    assert instance.enabled == form_data['enabled']
    assert instance.crontab.minute == str(config['minute'])
    assert instance.crontab.hour == str(config['hour'])
    assert instance.crontab.day_of_week == str(config['day_of_week'])
    assert total == 1

  def test_invalid_post_access_to_updateview(self, login_process, create_snapshots):
    user, snapshot = create_snapshots
    client, _ = login_process(user=factories.UserFactory())
    params = json.dumps({'user_pk': user.pk, 'snapshot_pk': snapshot.pk})
    target = factories.PeriodicTaskFactory(kwargs=params, enabled=False)
    form_data = self.form_data
    form_data['snapshot'] = snapshot.pk
    response = client.post(
      self.update_url(target.pk),
      data=urlencode(form_data),
      content_type='application/x-www-form-urlencoded',
    )
    instance = models.PeriodicTask.objects.get(pk=target.pk)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert instance.name == target.name
    assert instance.enabled == target.enabled
    assert instance.kwargs == target.kwargs

  # ==========
  # DeleteView
  # ==========
  def test_access_to_deleteview(self, login_process, create_snapshots):
    user, snapshot = create_snapshots
    client, user = login_process(user=user)
    instance = factories.PeriodicTaskFactory(kwargs=json.dumps({'user_pk': user.pk, 'snapshot_pk': snapshot.pk}))
    response = client.get(self.delete_url(instance.pk))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  def test_access_to_deleteview_without_authentication(self, client, create_snapshots):
    user, snapshot = create_snapshots
    instance = factories.PeriodicTaskFactory(kwargs=json.dumps({'user_pk': user.pk, 'snapshot_pk': snapshot.pk}))
    response = client.get(self.delete_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_deleteview(self, login_process, create_snapshots):
    user, snapshot = create_snapshots
    client, user = login_process(user=user)
    params = json.dumps({'user_pk': user.pk, 'snapshot_pk': snapshot.pk})
    target = factories.PeriodicTaskFactory(kwargs=params)
    response = client.post(self.delete_url(target.pk))
    total = models.PeriodicTask.objects.filter(kwargs__contains=params).count()

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_url
    assert total == 0

  def test_invalid_post_access_to_deleteview(self, login_process, create_snapshots):
    user, snapshot = create_snapshots
    client, _ = login_process(user=factories.UserFactory())
    params = json.dumps({'user_pk': user.pk, 'snapshot_pk': snapshot.pk})
    target = factories.PeriodicTaskFactory(kwargs=params)
    response = client.post(self.delete_url(target.pk))
    total = models.PeriodicTask.objects.filter(kwargs__contains=params).count()

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert total == 1

# ==========
# StockViews
# ==========
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
class TestStockViews(SharedFixture):
  list_url = reverse('stock:list_stock')
  download_url = reverse('stock:download_stock')

  # ========
  # ListView
  # ========
  def test_access_to_listview(self, wrap_login):
    client, _ = wrap_login
    response = client.get(self.list_url)

    assert response.status_code == status.HTTP_200_OK

  def test_access_to_listview_without_authentication(self, client):
    url = self.list_url
    response = client.get(url)
    expected = '{}?next={}'.format(self.login_url, url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == expected

  @pytest.mark.parametrize([
    'query_params',
    'num',
  ], [
    ({'condition': 'price < 100'}, 3),
    ({'condition': 100}, 4),
    ({}, 5),
  ], ids=[
    'qs-is-3-with-condition',
    'qs-is-4-with-integer',
    'qs-is-5-without-condition',
  ])
  def test_access_with_query(self, mocker, wrap_login, get_stock_records, query_params, num):
    stocks = get_stock_records
    client, _ = wrap_login
    exact_qs = models.Stock.objects.filter(pk__in=self.get_pks(stocks[:num]))
    mocker.patch('stock.forms.StockSearchForm.get_queryset_with_condition', return_value=exact_qs)
    mocker.patch('stock.models.get_language', return_value='en')
    response = client.get(self.list_url, query_params=query_params)

    assert response.status_code == status.HTTP_200_OK
    assert response.context['form'] is not None
    assert response.context['stocks'].count() == exact_qs.count()
    assertQuerySetEqual(response.context['stocks'], exact_qs, ordered=False)

  def test_post_invalid_access(self, wrap_login):
    client, _ = wrap_login
    response = client.post(self.list_url)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  # ============
  # DownloadPage
  # ============
  def test_access_to_download_stock_page(self, wrap_login):
    client, _ = wrap_login
    response = client.get(self.download_url)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  def test_access_to_download_stock_page_without_authentication(self, client):
    response = client.get(self.download_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_post_access_to_download_stock_page(self, mocker, wrap_login):
    client, user = wrap_login
    output = {
      'rows': (row for row in [['0001'], ['0002']]),
      'header': ['Code'],
      'filename': 'stock-test001.csv',
    }
    mocker.patch('stock.forms.StockDownloadForm.create_response_kwargs', return_value=output)
    params = {
      'filename': 'dummy-name',
    }
    expected = bytes('Code\n0001\n0002\n', 'utf-8')
    # Post access
    response = client.post(self.download_url, data=params)
    cookie = response.cookies.get('stock_download_status')
    attachment = response.get('content-disposition')
    stream = response.getvalue()

    assert response.has_header('content-disposition')
    assert output['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert cookie.value == 'completed'
    assert expected in stream

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
  def test_invalid_post_request_to_download_stock_page(self, wrap_login, params, expected_cond, expected_order):
    client, _ = wrap_login
    # Post access
    response = client.post(self.download_url, data=params)
    query_string = urllib.parse.quote('condition={}&ordering={}'.format(expected_cond, expected_order))
    location = '{}?{}'.format(self.list_url, query_string)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == location

# ================
# ExplanationViews
# ================
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
class TestExplanationViews(SharedFixture):
  template_url = reverse('stock:explanation')

  def test_access_to_explanation(self, wrap_login):
    client, _ = wrap_login
    response = client.get(self.template_url)

    assert response.status_code == status.HTTP_200_OK
    assertTemplateUsed(response, 'stock/explanation.html')

  def test_access_to_explanation_without_authentication(self, client):
    url = self.template_url
    response = client.get(url)
    expected = '{}?next={}'.format(self.login_url, url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == expected