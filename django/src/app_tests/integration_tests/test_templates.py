import pytest
import json
from webtest.app import AppError
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import datetime, timezone
from decimal import Decimal
from app_tests import status
from . import factories

UserModel = get_user_model()

# Get current path based on request parameter
def get_current_path(response):
  return response.context['request'].path
# Get date based on tuple data (yyyy,mm,dd)
get_date = lambda ymd: datetime(*ymd, 1, 2, 3, tzinfo=timezone.utc)

# ===================
# Account application
# ===================
# Index page
@pytest.mark.webtest
def test_access_to_index_page(csrf_exempt_django_app):
  app = csrf_exempt_django_app
  url = reverse('account:index')
  response = app.get(url)

  assert response.status_code == status.HTTP_200_OK
  assert 'Index' in str(response)

# Login page
@pytest.mark.webtest
def test_can_move_to_login_page(csrf_exempt_django_app):
  app = csrf_exempt_django_app
  login_url = reverse('account:login')
  page = app.get(reverse('account:index'))
  response = page.click('Login')

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == login_url

@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'arg_type'
], [
  ('username',),
  ('email', )
], ids=lambda val: f'login-{val}')
def test_login(csrf_exempt_django_app, arg_type):
  app = csrf_exempt_django_app
  params = {
    'username': 'test-user',
    'email': 'user@test.com',
    'password': 'test-password',
  }
  user = UserModel.objects.create_user(**params)
  # Get form and submit form
  forms = app.get(reverse('account:login')).forms
  form = forms['login-form']
  form['username'] = params[arg_type]
  form['password'] = params['password']
  response = form.submit().follow()

  assert response.context['user'].username == params['username']

@pytest.mark.webtest
@pytest.mark.django_db
def test_can_move_to_parent_page_from_login_page(csrf_exempt_django_app):
  app = csrf_exempt_django_app
  page = app.get(reverse('account:login'))
  response = page.click('Cancel')

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == reverse('account:index')

@pytest.fixture
def init_webtest(django_db_blocker, csrf_exempt_django_app):
  with django_db_blocker.unblock():
    owner, other = factories.UserFactory.create_batch(2)
  app = csrf_exempt_django_app
  users = {
    'owner': owner,
    'other': other,
  }

  return app, users

# Logout process
@pytest.mark.webtest
@pytest.mark.django_db
def test_logout(init_webtest):
  app, users = init_webtest
  url = reverse('account:index')
  # Get form and submit form
  forms = app.get(url, user=users['owner']).forms
  form = forms['logout-form']
  response = form.submit().follow()

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == url

# User profile page
@pytest.mark.webtest
@pytest.mark.django_db
def test_can_move_to_user_profile_page(init_webtest):
  app, users = init_webtest
  owner = users['owner']
  page = app.get(reverse('account:index'), user=owner)
  response = page.click('User Profile')

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == reverse('account:user_profile', kwargs={'pk': owner.pk})

@pytest.mark.webtest
@pytest.mark.django_db
def test_can_move_to_previous_page_from_user_profile_page(init_webtest):
  app, users = init_webtest
  owner = users['owner']
  page = app.get(reverse('account:user_profile', kwargs={'pk': owner.pk}), user=owner)
  response = page.click('Back')

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == reverse('account:index')

# Update user profile page
@pytest.mark.webtest
@pytest.mark.django_db
def test_can_move_to_update_user_profile_page(init_webtest):
  app, users = init_webtest
  owner = users['owner']
  pk = owner.pk
  page = app.get(reverse('account:user_profile', kwargs={'pk': pk}), user=owner)
  response = page.click('Update user profile')

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == reverse('account:update_profile', kwargs={'pk': pk})

@pytest.mark.webtest
@pytest.mark.django_db
def test_update_user_profile(csrf_exempt_django_app):
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
  forms = app.get(reverse('account:update_profile', kwargs={'pk': pk}), user=user).forms
  form = forms['user-profile-form']
  form['screen_name'] = new_screen_name
  response = form.submit().follow()
  new_user = response.context['user']

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == reverse('account:user_profile', kwargs={'pk': pk})
  assert new_user.username == params['username']
  assert new_user.email == params['email']
  assert new_user.screen_name == new_screen_name

@pytest.mark.webtest
@pytest.mark.django_db
def test_can_move_to_parent_page_from_update_user_profile_page(init_webtest):
  app, users = init_webtest
  owner = users['owner']
  pk = owner.pk
  page = app.get(reverse('account:update_profile', kwargs={'pk': pk}), user=owner)
  response = page.click('Cancel')

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == reverse('account:user_profile', kwargs={'pk': pk})

############################
# Invalid cases in account #
############################
@pytest.mark.webtest
@pytest.mark.django_db
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
def test_invalid_page_access_in_account(init_webtest, page_link, method, params):
  app, users = init_webtest
  
  with pytest.raises(AppError) as ex:
    url = reverse(f'account:{page_link}', kwargs={'pk': users['other'].pk})
    caller = getattr(app, method)
    caller(url, params=params, user=users['owner'])

  assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

# =================
# Stock application
# =================
# List page for each relevant model
@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'page_title',
  'page_link',
], [
  ('Dashboard', 'dashboard'),
  ('Snapshot list', 'list_snapshot'),
  ('Cash list', 'list_cash'),
  ('Purchased stock list', 'list_purchased_stock'),
], ids=[
  'dashboard-page',
  'cash-list-page',
  'purchased-stock-list-page',
  'snapshot-list-page',
])
def test_can_move_to_target_page_from_index_page(init_webtest, page_title, page_link):
  app, users = init_webtest
  page = app.get(reverse('account:index'), user=users['owner'])
  response = page.click(page_title)
  exact_url = reverse(f'stock:{page_link}')

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == exact_url

# Page transition between list-page and registration-page
@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'base_page',
  'page_title',
  'page_link',
], [
  # from list page to register page
  ('dashboard', 'Register snapshot', 'register_snapshot'),
  ('list_snapshot', 'Register snapshot', 'register_snapshot'),
  ('list_cash', 'Register cash', 'register_cash'),
  ('list_purchased_stock', 'Register purchsed stock', 'register_purchased_stock'),
  # from register page to list page
  ('register_snapshot', 'Cancel', 'list_snapshot'),
  ('register_cash', 'Cancel', 'list_cash'),
  ('register_purchased_stock', 'Cancel', 'list_purchased_stock'),
], ids=[
  'register-page-from-dashboard-page',
  'register-page-from-snapshot-list-page',
  'register-page-from-cash-list-page',
  'register-page-from-purchased-stock-list-page',
  'list-page-from-snapshot-registration-page',
  'list-page-from-cash-registration-page',
  'list-page-from-purchased-stock-registration-page',
])
def test_can_move_to_related_page_between_list_and_registration_in_stock(init_webtest, base_page, page_title, page_link):
  app, users = init_webtest
  page = app.get(reverse(f'stock:{base_page}'), user=users['owner'])
  response = page.click(page_title)
  exact_url = reverse(f'stock:{page_link}')

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == exact_url

# Page transition between list-page and update-page
@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'base_page',
  'factory_class',
  'page_link',
], [
  # from list page to update page
  ('list_snapshot', factories.SnapshotFactory, 'update_snapshot'),
  ('list_cash', factories.CashFactory, 'update_cash'),
  ('list_purchased_stock', factories.PurchasedStockFactory, 'update_purchased_stock'),
], ids=[
  'update-snapshot-page-from-list-page',
  'update-cash-page-from-list-page',
  'update-purchased-stock-page-from-list-page',
])
def test_can_move_to_update_page_in_stock(init_webtest, base_page, factory_class, page_link):
  app, users = init_webtest
  owner = users['owner']
  instance = factory_class(user=owner)
  target_url = reverse(f'stock:{page_link}', kwargs={'pk': instance.pk})
  page = app.get(reverse(f'stock:{base_page}'), user=owner)
  response = page.click(href=target_url)

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == target_url

@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'base_page',
  'factory_class',
  'page_link',
], [
  # from update page to list page
  ('update_snapshot', factories.SnapshotFactory, 'list_snapshot'),
  ('update_cash', factories.CashFactory, 'list_cash'),
  ('update_purchased_stock', factories.PurchasedStockFactory, 'list_purchased_stock'),
], ids=[
  'snapshot-list-page-from-update-page',
  'cash-list-page-from-update-page',
  'purchased-stock-list-page-from-update-page',
])
def test_can_move_to_list_page_in_stock(init_webtest, base_page, factory_class, page_link):
  app, users = init_webtest
  owner = users['owner']
  instance = factory_class(user=owner)
  target_url = reverse(f'stock:{page_link}')
  page = app.get(reverse(f'stock:{base_page}', kwargs={'pk': instance.pk}), user=owner)
  response = page.click('Cancel')

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == target_url

# Check list items
@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'list_page',
  'factory_class',
  'object_name',
], [
  # from update page to list page
  ('list_snapshot', factories.SnapshotFactory, 'snapshots'),
  ('list_cash', factories.CashFactory, 'cashes'),
  ('list_purchased_stock', factories.PurchasedStockFactory, 'pstocks'),
], ids=[
  'count-snapshots-owned-by-user',
  'count-cashes-owned-by-user',
  'count-purchased-stock-owned-by-user',
])
def test_count_owned_items_in_stock(init_webtest, list_page, factory_class, object_name):
  app, users = init_webtest
  owner = users['owner']
  other = users['other']
  _ = factory_class.create_batch(2, user=owner)
  _ = factory_class.create_batch(3, user=other)
  response = app.get(reverse(f'stock:{list_page}'), user=owner)

  assert response.status_code == status.HTTP_200_OK
  assert len(response.context[object_name]) == 2

# Registration form
@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'target_page',
  'form_id',
  'param_name',
  'success_link',
], [
  ('register_snapshot', 'snapshot-form', 'snapshot', 'list_snapshot'),
  ('register_cash', 'cash-form', 'cash', 'list_cash'),
  ('register_purchased_stock', 'purchased-stock-form', 'pstock', 'list_purchased_stock'),
], ids=[
  'snapshot-registration-page',
  'cash-registration-page',
  'purchased-stock-registration-page',
])
def test_registration_form_in_stock(init_webtest, target_page, form_id, param_name, success_link):
  stock = factories.StockFactory(name='sample-stock', code='a9028')

  inputs = {
    'snapshot': {
      'title': 'sample-snapshot',
      'start_date': '2024-12-3',
      'end_date': '2025-1-21',
    },
    'cash': {
      'balance': 1023,
      'registered_date': '2023-3-5',
    },
    'pstock': {
      'stock': stock.pk,
      'price': 4356.78,
      'purchase_date': '2024-9-22',
      'count': 100,
    },
  }
  instances = {
    'snapshot': 'snapshots',
    'cash': 'cashes',
    'pstock': 'pstocks',
  }
  exacts = {
    'snapshot': {
      'title':     'sample-snapshot', 
      'startDate': '2024-12-03',
      'endDate':   '2025-01-21',
    },
    'cash': {
      'balance':        '1,023',
      'registeredDate': '2023-03-05',
    },
    'pstock': {
       'code':         stock.code,
       'name':         stock.name,
       'industry':     stock.industry.name,
       'purchaseDate': '2024-09-22',
       'price':        '4,356.78',
       'count':        '100',
    },
  }

  # ------------
  # main routine
  # ------------
  app, users = init_webtest
  forms = app.get(reverse(f'stock:{target_page}'), user=users['owner']).forms
  form = forms[form_id]
  # Update form data
  for key, val in inputs[param_name].items():
    form[key] = val
  response = form.submit().follow()
  # Collect response data
  records = response.context[instances[param_name]]
  elements = {
    element.attrs['data-type']: element.contents[0]
    for element in response.html.find_all('td', attrs={'data-type': True})
  }
  exact_vals = exacts[param_name]

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == reverse(f'stock:{success_link}')
  assert len(records) == 1
  assert all([elements[key] == _exactval for key, _exactval in exact_vals.items()])

# Update form
@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'param_name',
], [
  ('snapshot',),
  ('cash',),
  ('pstock',),
], ids=[
  'snapshot-update-page',
  'cash-update-page',
  'purchased-stock-update-page',
])
def test_update_form_in_stock(init_webtest, param_name):
  app, _users = init_webtest
  user = _users['owner']
  stock = factories.StockFactory(name='target-stock', code='796a')
  # Define all data
  kwargs = {
    'snapshot': {
      'page_name': 'update_snapshot',
      'factory': factories.SnapshotFactory,
      'args': {
        'title': 'old-snapshot',
        'start_date': get_date((1999,12,3)),
        'end_date': get_date((2001,1,21)),
      },
      'updated': {
        'title': 'updated-snapshot',
        'start_date': '2010-1-4',
        'end_date': '2011-02-15',
      },
      'form-id': 'snapshot-form',
      'object_name': 'snapshots',
      'success_link': 'list_snapshot',
    },
    'cash': {
      'page_name': 'update_cash',
      'factory': factories.CashFactory,
      'args': {
        'balance': 1024,
        'registered_date': get_date((2012,3,4)),
      },
      'updated': {
        'balance': 2048,
        'registered_date': '2022-10-1',
      },
      'form-id': 'cash-form',
      'object_name': 'cashes',
      'success_link': 'list_cash',
    },
    'pstock': {
      'page_name': 'update_purchased_stock',
      'factory': factories.PurchasedStockFactory,
      'args': {
        'stock': stock,
        'price': Decimal('43.1'),
        'purchase_date': get_date((2002,9,5)),
        'count': 100,
      },
      'updated': {
        'stock': stock.pk,
        'price': Decimal('1052.01'),
        'purchase_date': '2012-8-17',
        'count': 2200,
      },
      'form-id': 'purchased-stock-form',
      'object_name': 'pstocks',
      'success_link': 'list_purchased_stock',
    },
  }
  exacts = {
    'snapshot': {
      'title':     'updated-snapshot', 
      'startDate': '2010-01-04',
      'endDate':   '2011-02-15',
    },
    'cash': {
      'balance':        '2,048',
      'registeredDate': '2022-10-01',
    },
    'pstock': {
       'code':         stock.code,
       'name':         stock.name,
       'industry':     stock.industry.name,
       'purchaseDate': '2012-08-17',
       'price':        '1,052.01',
       'count':        '2,200',
    },
  }
  # Get relevant data
  options = kwargs[param_name]
  # Preparation
  factory_class = options['factory']
  instance = factory_class(user=user, **options['args'])
  # Execution
  forms = app.get(reverse(f'stock:{options["page_name"]}', kwargs={'pk': instance.pk}), user=user).forms
  form = forms[options['form-id']]
  for key, val in options['updated'].items():
    form[key] = val
  response = form.submit().follow()
  # Collect response data
  records = response.context[options['object_name']]
  elements = {
    element.attrs['data-type']: element.contents[0]
    for element in response.html.find_all('td', attrs={'data-type': True})
  }
  exact_vals = exacts[param_name]

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == reverse(f'stock:{options["success_link"]}')
  assert len(records) == 1
  assert all([elements[key] == _exactval for key, _exactval in exact_vals.items()])

# Delete form
@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'factory_class',
  'delete_link',
  'list_link',
  'object_name',
], [
  (factories.SnapshotFactory, 'delete_snapshot', 'list_snapshot', 'snapshots'),
  (factories.CashFactory, 'delete_cash', 'list_cash', 'cashes'),
  (factories.PurchasedStockFactory, 'delete_purchased_stock', 'list_purchased_stock', 'pstocks'),
], ids=[
  'snapshot-update-page',
  'cash-update-page',
  'purchased-stock-update-page',
])
def test_delete_instance_in_stock(init_webtest, factory_class, delete_link, list_link, object_name):
  app, _user = init_webtest
  user = _user['owner']
  target, rest = factory_class.create_batch(2, user=user)
  url = reverse(f'stock:{list_link}')
  forms = app.get(url, user=user).forms
  form = forms['delete-form']
  form.action = reverse(f'stock:{delete_link}', kwargs={'pk': target.pk})
  response = form.submit().follow()

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == url
  assert len(response.context[object_name]) == 1
  assert response.context[object_name].first().pk == rest.pk

# Check dashboard
@pytest.mark.webtest
@pytest.mark.django_db
def test_check_snapshot_detail_in_dashboard(init_webtest):
  app, _users = init_webtest
  user = _users['owner']
  # Create cash and purchased-stocks
  _ = factories.CashFactory(
    user=user,
    balance=123456,
    registered_date=get_date((2010,2,3)),
  )
  cash = factories.CashFactory(
    user=user,
    balance=234567,
    registered_date=get_date((2021,12,3)),
  )
  stock1 = factories.StockFactory(name='stock1', code='4321')
  stock2 = factories.StockFactory(name='stock2', code='dcba')
  ps_1st = factories.PurchasedStockFactory(
    user=user,
    stock=stock1,
    price=Decimal('123.01'),
    purchase_date=get_date((2022,3,2)),
    count=100,
  )
  _ = factories.PurchasedStockFactory(
    user=user,
    stock=stock2,
    price=Decimal('114.21'),
    purchase_date=get_date((2021,3,4)),
    count=332,
  )
  ps_3rd = factories.PurchasedStockFactory(
    user=user,
    stock=stock2,
    price=Decimal('1145.15'),
    purchase_date=get_date((2021,12,9)),
    count=510,
  )
  _ = factories.PurchasedStockFactory(
    user=user,
    stock=stock1,
    price=Decimal('245.89'),
    purchase_date=get_date((2022,3,3)),
    count=540,
  )
  ps_2nd = factories.PurchasedStockFactory(
    user=user,
    stock=stock1,
    price=Decimal('2345.99'),
    purchase_date=get_date((2022,1,12)),
    count=1020,
  )
  snapshot = factories.SnapshotFactory(
    user=user,
    title='sample',
    start_date=get_date((2021,3,5)),
    end_date=get_date((2022,3,2)),
  )
  # Expected data
  expected = {
    'cash': cash.get_dict(),
    'purchased_stocks': [
      ps_1st.get_dict(),
      ps_2nd.get_dict(),
      ps_3rd.get_dict(),
    ],
  }
  compare_dict = lambda _est_dict, _exact_dict: all([_est_dict[key] == val for key, val in _exact_dict.items()]) 
  # Execution
  uuid = str(snapshot.uuid)
  response = app.get(reverse('stock:dashboard'), user=user)
  element = response.html.find('script', id=uuid)
  estimated = json.loads(element.contents[0])

  assert all([key in estimated.keys() for key in ['cash', 'purchased_stocks']])
  assert compare_dict(estimated['cash'], expected['cash'])
  assert all([
    compare_dict(est_dict, exact_dict)
    for est_dict, exact_dict in zip(estimated['purchased_stocks'], expected['purchased_stocks'])
  ])

##########################
# Invalid cases in stock #
##########################
@pytest.mark.webtest
@pytest.mark.parametrize([
  'target_page',
], [
  ('dashboard',),
  ('list_snapshot',),
  ('list_cash',),
  ('list_purchased_stock',),
], ids=[
  'dashboard-page',
  'snapshot-list-page',
  'cash-list-page',
  'purchased-stock-list-page',
])
def test_redirect_login_page_without_authentication(csrf_exempt_django_app, target_page):
  app = csrf_exempt_django_app
  response = app.get(reverse(f'stock:{target_page}')).follow()

  assert response.status_code == status.HTTP_200_OK
  assert get_current_path(response) == reverse('account:login')

@pytest.mark.webtest
@pytest.mark.parametrize([
  'target_page',
], [
  ('register_snapshot',),
  ('register_cash',),
  ('register_purchased_stock',),
], ids=[
  'snapshot-registration-page',
  'cash-registration-page',
  'purchased-stock-registration-page',
])
def test_cannot_move_to_target_page_without_authentication(csrf_exempt_django_app, target_page):
  app = csrf_exempt_django_app

  with pytest.raises(AppError) as ex:
    app.get(reverse(f'stock:{target_page}'))

  assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'page_link',
  'factory_class',
], [
  ('update_snapshot', factories.SnapshotFactory),
  ('update_cash', factories.CashFactory),
  ('update_purchased_stock', factories.PurchasedStockFactory),
], ids=[
  'invalid-access-to-update-snapshot-page',
  'invalid-access-to-update-cash-page',
  'invalid-access-to-update-purchased-stock-page',
])
def test_cannot_access_update_page_except_owner(init_webtest, page_link, factory_class):
  app, users = init_webtest
  owner = users['owner']
  other = users['other']
  instance = factory_class(user=owner)

  with pytest.raises(AppError) as ex:
    app.get(reverse(f'stock:{page_link}', kwargs={'pk': instance.pk}), user=other)

  assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'page_link',
  'factory_class',
  'form_id',
], [
  ('update_snapshot', factories.SnapshotFactory, 'snapshot-form'),
  ('update_cash', factories.CashFactory, 'cash-form'),
  ('update_purchased_stock', factories.PurchasedStockFactory, 'purchased-stock-form'),
], ids=[
  'invalid-post-method-in-snapshot',
  'invalid-post-method-in-cash',
  'invalid-post-method-in-purchased-stock',
])
def test_invalid_post_method_in_update_page(init_webtest, page_link, factory_class, form_id):
  app, users = init_webtest
  owner = users['owner']
  other = users['other']
  instance = factory_class(user=owner)
  forms = app.get(reverse(f'stock:{page_link}', kwargs={'pk': instance.pk}), user=owner).forms
  form = forms[form_id]

  with pytest.raises(AppError) as ex:
    form.submit(user=other)

  assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

@pytest.mark.webtest
@pytest.mark.django_db
@pytest.mark.parametrize([
  'param_name',
], [
  ('snapshot',),
  ('cash',),
  ('pstock',),
], ids=lambda val: f'invalid-delete-request-in-{val}')
def test_invalid_request_for_delete_method(init_webtest, param_name):
  app, _users = init_webtest
  owner = _users['owner']
  other = _users['other']

  kwargs = {
    'snapshot': {
      'factory_class': factories.SnapshotFactory,
      'delete_link': 'delete_snapshot',
      'list_link': 'list_snapshot',
    },
    'cash': {
      'factory_class': factories.CashFactory,
      'delete_link': 'delete_cash',
      'list_link': 'list_cash',
    },
    'pstock': {
      'factory_class': factories.PurchasedStockFactory,
      'delete_link': 'delete_purchased_stock',
      'list_link': 'list_purchased_stock',
    },
  }
  options = kwargs[param_name]
  factory_class = options['factory_class']
  instance = factory_class(user=other)
  forms = app.get(reverse(f'stock:{options["list_link"]}'), user=owner).forms
  form = forms['delete-form']
  form.action = reverse(f'stock:{options["delete_link"]}', kwargs={'pk': instance.pk})

  with pytest.raises(AppError) as ex:
    form.submit()
  
  assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

# ============================
# Check a series of processing
# ============================
@pytest.mark.webtest
@pytest.mark.django_db
def test_check_a_seires_of_processing(csrf_exempt_django_app):
  app = csrf_exempt_django_app
  user_params = {
    'username': 'test',
    'email': 'test@user.com',
    'password': 'user-pass',
    'screen_name': 'sample-user',
  }
  user = UserModel.objects.create_user(**user_params)
  stocks = factories.StockFactory.create_batch(128)[:5]
  status_codes = []
  results = []

  # Step1: login
  form = app.get(reverse('account:login')).forms['login-form']
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
    {'stock':stocks[0].pk,'price':Decimal('1001.1' ),'purchase_date':'2021-03-13','count':100}, # 100,110
    {'stock':stocks[1].pk,'price':Decimal(  '99.9' ),'purchase_date': '2021-04-1','count':200}, #  19,980
    {'stock':stocks[2].pk,'price':Decimal('1010.5' ),'purchase_date': '2021-4-28','count':100}, # 101,050
    {'stock':stocks[1].pk,'price':Decimal( '121.0' ),'purchase_date': '2021-5-11','count':100}, #  12,100
    {'stock':stocks[2].pk,'price':Decimal('1111.5' ),'purchase_date': '2021-6-09','count':200}, # 222,300
    {'stock':stocks[3].pk,'price':Decimal( '296.71'),'purchase_date': '2021-8-11','count':200}, # 135.118
    {'stock':stocks[2].pk,'price':Decimal('1123.3' ),'purchase_date':'2021-09-02','count':100}, # 112,330
    # Ignore the following record (2021/10/11) when snapshot is created
    {'stock':stocks[4].pk,'price':Decimal('3030.11'),'purchase_date':'2021-10-11','count':100}, # 303,011
    # From 2021/12/4 to 2022/2/2
    {'stock':stocks[4].pk,'price':Decimal('4801'   ),'purchase_date':'2021-12-10','count':100}, # 480,100
    {'stock':stocks[0].pk,'price':Decimal( '990.7' ),'purchase_date': '2022-01-5','count':200}, # 198,140
    {'stock':stocks[1].pk,'price':Decimal( '130.59'),'purchase_date':'2022-01-20','count':200}, #  26,118
    {'stock':stocks[3].pk,'price':Decimal( '360.13'),'purchase_date': '2022-1-25','count':300}, # 108,039
    {'stock':stocks[2].pk,'price':Decimal('1100.88'),'purchase_date': '2022-1-28','count':100}, # 110,088
  ]
  # Execute form process
  for params in options:
    res = app.get(next_link).click('Register purchsed stock')
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
  # There are more than ten records, so move to next page
  total_pstocks  = len(page.context['pstocks'])
  page = page.click(linkid='next-page')
  total_pstocks += len(page.context['pstocks'])
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
  details = []
  # Collect detail of snapshots (ordering: '-created_at')
  for ss in snapshots:
    uuid = str(ss.uuid)
    element = res.html.find('script', id=uuid)
    details.append(json.loads(element.contents[0]))

  # --------------
  # Assert process
  # --------------
  calc_pstock_sum = lambda ps_records: sum([target['price'] * target['count'] for target in ps_records]) 
  # Check status_codes and results
  assert all([_status_code == status.HTTP_200_OK for _status_code in status_codes])
  assert all(results)
  # Check cashes
  assert details[2]['cash']['balance'] == 750000
  assert details[2]['cash']['registered_date'] == '2020-12-11'
  assert details[1]['cash']['balance'] == 122788
  assert details[1]['cash']['registered_date'] == '2021-09-10'
  assert details[0]['cash']['balance'] == 77516
  assert details[0]['cash']['registered_date'] == '2022-02-02'
  # Check purchsed stock
  assert calc_pstock_sum(details[2]['purchased_stocks']) == 0
  assert calc_pstock_sum(details[1]['purchased_stocks']) == 627212
  assert calc_pstock_sum(details[0]['purchased_stocks']) == 922485
