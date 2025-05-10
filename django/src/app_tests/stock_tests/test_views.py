import pytest
import json
from django.urls import reverse
from app_tests import status
from datetime import datetime, timezone
from urllib.parse import urlencode
from stock import models
from . import factories

@pytest.fixture
def login_process(client, django_db_blocker):
  with django_db_blocker.unblock():
    user = factories.UserFactory()
    client.force_login(user)

  return client, user

@pytest.fixture(params=['cash', 'purchased_stock', 'snapshot'], ids=lambda val: f'link-{val}')
def get_link(request):
  yield request.param

@pytest.fixture
def get_cash_kwargs():
  link = 'cash'
  form_data = {
    'balance': 12345,
    'registered_date': datetime(2020,10,12,4,8,19, tzinfo=timezone.utc),
  }
  model_class = models.Cash
  factory_class = factories.CashFactory

  return link, form_data, model_class, factory_class

@pytest.fixture
def get_purchased_stock_kwargs(django_db_blocker):
  with django_db_blocker.unblock():
    stock = factories.StockFactory()

  link = 'purchased_stock'
  form_data = {
    'stock': stock.pk,
    'price': 5678,
    'purchase_date': datetime(2022,3,7,11,5,21, tzinfo=timezone.utc),
    'count': 120,
  }
  model_class = models.PurchasedStock
  factory_class = factories.PurchasedStockFactory

  return link, form_data, model_class, factory_class

@pytest.fixture
def get_snapshot_kwargs():
  link = 'snapshot'
  form_data = {
    'title': 'sample-snapshot',
    'start_date': datetime(2023,4,5,12,3,10, tzinfo=timezone.utc),
    'end_date':   datetime(2023,7,9,13,1,32, tzinfo=timezone.utc),
  }
  model_class = models.Snapshot
  factory_class = factories.SnapshotFactory

  return link, form_data, model_class, factory_class

@pytest.fixture(params=['cash', 'purchased_stock', 'snapshot'])
def get_kwargs(request):
  if request.param == 'cash':
    link, form_data, model_class, factory_class = request.getfixturevalue('get_cash_kwargs')
  elif request.param == 'purchased_stock':
    link, form_data, model_class, factory_class = request.getfixturevalue('get_purchased_stock_kwargs')
  elif request.param == 'snapshot':
    link, form_data, model_class, factory_class = request.getfixturevalue('get_snapshot_kwargs')

  return link, form_data, model_class, factory_class

# =========
# Dashboard
# =========
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_get_access_to_dashboard_page(login_process):
  client, user = login_process
  client.force_login(user)
  url = reverse('stock:dashboard')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.stock
@pytest.mark.view
def test_without_authentication_for_dashboard(client):
  url = reverse('stock:dashboard')
  response = client.get(url)
  expected = '{}?next={}'.format(reverse('account:login'), url)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == expected

# ========
# AjaxView
# ========
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_get_access_to_ajaxview(client):
  stocks = [
    factories.StockFactory(name='stock01', code='0001'),
    factories.StockFactory(name='stock02', code='0002'),
  ]
  url = reverse('stock:ajax_stock')
  response = client.get(url)
  query = json.loads(response.content)
  data = query['qs']
  keys = ['pk', 'name', 'code']

  assert all([
    all([key in item.keys() for key in keys]) for item in data
  ])
  assert len(stocks) == len(data)
  assert all([
    all([getattr(_stock, key) == item[key] for key in keys])
    for _stock, item in zip(stocks, data)
  ])

# ========
# ListView
# ========
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_get_access_to_listview(login_process, get_link):
  client, user = login_process
  link = get_link
  client.force_login(user)
  url = reverse(f'stock:list_{link}')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.stock
@pytest.mark.view
def test_without_authentication_in_listview(client, get_link):
  link = get_link
  url = reverse(f'stock:list_{link}')
  response = client.get(url)
  expected = '{}?next={}'.format(reverse('account:login'), url)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == expected

# ==========
# CreateView
# ==========
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_get_access_to_createview(login_process, get_link):
  client, user = login_process
  link = get_link
  client.force_login(user)
  url = reverse(f'stock:register_{link}')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.stock
@pytest.mark.view
def test_without_authentication_in_createview(client, get_link):
  link = get_link
  url = reverse(f'stock:register_{link}')
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_post_access_to_createview(login_process, get_kwargs):
  client, user = login_process
  link, form_data, model_class, _ = get_kwargs
  url = reverse(f'stock:register_{link}')
  response = client.post(url, data=form_data)
  total = model_class.objects.filter(user=user).count()

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse(f'stock:list_{link}')
  assert total == 1

# ==========
# UpdateView
# ==========
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_get_access_to_updateview(login_process, get_kwargs):
  client, user = login_process
  link, _, _, factory_class = get_kwargs
  instance = factory_class(user=user)
  url = reverse(f'stock:update_{link}', kwargs={'pk': instance.pk})
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_without_authentication_in_updateview(client, get_kwargs):
  user = factories.UserFactory()
  link, _, _, factory_class = get_kwargs
  instance = factory_class(user=user)
  url = reverse(f'stock:update_{link}', kwargs={'pk': instance.pk})
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_valid_post_access_to_updateview(login_process, get_kwargs):
  client, user = login_process
  link, form_data, model_class, factory_class = get_kwargs
  target = factory_class(user=user)
  pk = target.pk
  url = reverse(f'stock:update_{link}', kwargs={'pk': pk})
  response = client.post(url, data=urlencode(form_data), content_type='application/x-www-form-urlencoded')
  instance = model_class.objects.get(pk=pk)
  total = model_class.objects.filter(user=user).count()

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse(f'stock:list_{link}')
  assert all([
    getattr(instance, key) == val if key != 'stock' else instance.stock.pk == val
    for key, val in form_data.items()
  ])
  assert total == 1

@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_post_access_to_updateview(login_process, get_kwargs):
  client, _ = login_process
  other = factories.UserFactory()
  link, form_data, model_class, factory_class = get_kwargs
  target = factory_class(user=other)
  pk = target.pk
  url = reverse(f'stock:update_{link}', kwargs={'pk': pk})
  response = client.post(url, data=urlencode(form_data), content_type='application/x-www-form-urlencoded')
  instance = model_class.objects.get(pk=pk)

  assert response.status_code == status.HTTP_403_FORBIDDEN
  all([
    getattr(target, key) == getattr(instance, key) if key != 'stock' else target.stock.pk == instance.stock.pk
    for key in form_data.keys()
  ])

# ==========
# DeleteView
# ==========
@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_get_access_to_deleteview(login_process, get_kwargs):
  client, user = login_process
  link, _, _, factory_class = get_kwargs
  instance = factory_class(user=user)
  url = reverse(f'stock:delete_{link}', kwargs={'pk': instance.pk})
  response = client.get(url)

  assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_without_authentication_in_deleteview(client, get_kwargs):
  user = factories.UserFactory()
  link, _, _, factory_class = get_kwargs
  instance = factory_class(user=user)
  url = reverse(f'stock:delete_{link}', kwargs={'pk': instance.pk})
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_valid_post_access_to_deleteview(login_process, get_kwargs):
  client, user = login_process
  link, _, model_class, factory_class = get_kwargs
  target = factory_class(user=user)
  pk = target.pk
  url = reverse(f'stock:delete_{link}', kwargs={'pk': pk})
  response = client.post(url)
  total = model_class.objects.filter(user=user).count()

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse(f'stock:list_{link}')
  assert total == 0

@pytest.mark.stock
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_post_access_to_deleteview(login_process, get_kwargs):
  client, _ = login_process
  other = factories.UserFactory()
  link, _, model_class, factory_class = get_kwargs
  target = factory_class(user=other)
  pk = target.pk
  url = reverse(f'stock:delete_{link}', kwargs={'pk': pk})
  response = client.post(url)
  total = model_class.objects.all().count()

  assert response.status_code == status.HTTP_403_FORBIDDEN
  assert total == 1