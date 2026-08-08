import pytest
from django.core.exceptions import ValidationError
from django.db import (
  DataError,
  models as DjangoModels
)
from django.db.utils import IntegrityError, DataError
from decimal import Decimal
from account import models
from app_tests import factories, get_date

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
class TestUser:
  def test_user_instance_type(self):
    user = factories.UserFactory.build()

    assert isinstance(user, models.User)

  @pytest.mark.parametrize([
    'username',
    'email',
    'kwargs',
  ], [
    ('hoge', 'hoge@example.com', {'screen_name': 'hogehoge'}),
    ('1'*128, '{}@ok.com'.format('1'*121), {'screen_name': '1'*128}),
    ('foo', 'foo@ok.com', {'screen_name': ''}),
    ('foo', 'foo@ok.com', {}),
  ], ids=[
    'valid-data',
    'max-length',
    'include-blank-data',
    'include-empty-data',
  ])
  def test_user_creation(self, username, email, kwargs):
    user = models.User.objects.create_user(
      username=username,
      email=email,
      **kwargs,
    )

    assert user.username == username
    assert user.email == email
    assert user.screen_name == kwargs.get('screen_name', '')

  def test_superuser_creation(self):
    base_user = factories.UserFactory.build()
    superuser = models.User.objects.create_superuser(
      username=base_user.username,
      email=base_user.email,
      is_staff=True,
      is_superuser=True,
    )
    assert superuser.is_staff
    assert superuser.is_superuser

  def test_superuser_is_not_staffuser(self):
    base_user = factories.UserFactory.build()
    err = 'Superuser must have is_staff=True.'

    with pytest.raises(ValueError) as ex:
      superuser = models.User.objects.create_superuser(
        username=base_user.username,
        email=base_user.email,
        is_staff=False,
        is_superuser=True,
      )
    assert err in ex.value.args

  def test_superuser_is_not_superuser(self):
    base_user = factories.UserFactory.build()
    err = 'Superuser must have is_superuser=True.'

    with pytest.raises(ValueError) as ex:
      superuser = models.User.objects.create_superuser(
        username=base_user.username,
        email=base_user.email,
        is_staff=True,
        is_superuser=False,
      )
    assert err in ex.value.args

  def test_empty_username(self):
    base_user = factories.UserFactory.build()
    err = 'The given username must be set'

    with pytest.raises(ValueError) as ex:
      models.User.objects.create_user(
        username='',
        email=base_user.email,
      )
    assert err in ex.value.args

  def test_empty_email(self):
    base_user = factories.UserFactory.build()
    err = 'The given email must be set'

    with pytest.raises(ValueError) as ex:
      models.User.objects.create_user(
        username=base_user.username,
        email='',
      )
    assert err in ex.value.args

  def test_invalid_username(self):
    with pytest.raises(DataError):
      base_user = factories.UserFactory.build()
      models.User.objects.create_user(
        username='1'*129,
        email=base_user.email,
      )

  def test_invalid_screen_name(self):
    with pytest.raises(DataError):
      base_user = factories.UserFactory.build()
      models.User.objects.create_user(
        username=base_user.username,
        email=base_user.email,
        screen_name='1'*129,
      )

  def test_invalid_same_username(self):
    base_user = factories.UserFactory()

    with pytest.raises(IntegrityError):
      models.User.objects.create_user(
        username=base_user.username,
        email=f'mail{base_user.pk}@example.com',
      )

  def test_invalid_same_email(self):
    base_user = factories.UserFactory()

    with pytest.raises(IntegrityError):
      models.User.objects.create_user(
        username=f'hoge{base_user.pk}',
        email=base_user.email,
      )

  @pytest.mark.parametrize([
    'username',
    'screen_name',
    'expected'
  ], [
    ('1'*32, '2'*32, '2'*32,),
    ('1'*32, '', '1'*32,),
    ('1'*32, '2'*33, '{}...'.format('2'*32)),
    ('1'*33, '', '{}...'.format('1'*32)),
  ], ids=[
    'length-eq-32',
    'screen-name-is-empty',
    'screen-name-length-is-33',
    'username-length-is-33',
  ])
  def test_check_shortname(self, username, screen_name, expected):
    user = factories.UserFactory(
      username=username,
      screen_name=screen_name,
    )

    assert user.get_short_name() == expected

  @pytest.mark.parametrize([
    'username',
    'screen_name',
    'expected',
  ], [
    ('1'*32, '2'*32, '2'*32,),
    ('1'*32, '', '1'*32,),
    ('1'*33, '2'*33, '2'*33),
    ('1'*33, '', '1'*33),
    ('1'*128, '2'*128, '2'*128),
    ('1'*128, '', '1'*128),
  ], ids=[
    'length-eq-32',
    'usename-length-eq-32-screen-name-is-empty',
    'length-eq-33',
    'username-length-eq-33-screen-name-is-empty',
    'length-eq-128',
    'username-length-eq-128-screen-name-is-empty',
  ])
  def test_check_fullname(self, username, screen_name, expected):
    user = factories.UserFactory(
      username=username,
      screen_name=screen_name,
    )

    assert user.get_full_name() == expected

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
class TestPortfolioUser:
  def _get_expressions(self, counts=5, investments=Decimal('2.00'), dividends=Decimal('5.00')):
    expressions = {
      'total_stock_counts': DjangoModels.Value(
        counts,
        output_field=DjangoModels.IntegerField(),
      ),
      'total_investments': DjangoModels.Value(
        investments,
        output_field=DjangoModels.DecimalField(max_digits=12, decimal_places=2),
      ),
      'total_dividends': DjangoModels.Value(
        dividends,
        output_field=DjangoModels.DecimalField(max_digits=10, decimal_places=2),
      ),
    }

    return expressions

  @pytest.fixture(scope='class')
  def get_normal_user(self, django_db_blocker):
    with django_db_blocker.unblock():
      user = factories.UserFactory()

    return user

  @pytest.fixture
  def common_mock(self, mocker):
    from stock.models import PurchasedStock

    def inner(**kwargs):
      return mocker.patch.object(
        PurchasedStock.objects,
        'get_summary_expressions',
        **kwargs,
      )

    return inner

  @pytest.mark.parametrize([
    'counts',
    'investments',
    'dividends',
  ],[
    (0, '0.00', '0.00'),
    (1, '0.01', '0.01'),
    (2, '2500000.00', '1200000.00'),
    (3, '9999999999.99', '99999999.99'),
  ], ids=[
    'zero-pattern',
    'min-pattern',
    'normal-pattern',
    'max-pattern',
  ])
  def test_valid_properties(self, common_mock, get_normal_user, counts, investments, dividends):
    total_investments = Decimal(investments)
    total_dividends = Decimal(dividends)
    dummy_expressions = self._get_expressions(counts, total_investments, total_dividends)
    mock_get_expressions = common_mock(return_value=dummy_expressions)
    # ------------
    # main routine
    # ------------
    user = get_normal_user
    portfolio = models.PortfolioUser.objects.get(pk=user.pk)

    mock_get_expressions.assert_called_once_with(relation_prefix='purchased_stocks')
    assert portfolio.purchased_stock_count == counts
    assert abs(float(portfolio.total_investment_amount) - float(total_investments)) < 1e-2
    assert abs(float(portfolio.total_dividends) - float(total_dividends)) < 1e-2

  @pytest.mark.parametrize([
    'investments',
    'dividends',
  ],[
    ('10000000000.00',  '99999999.99'),
    ( '9999999999.99', '100000000.00'),
  ], ids=[
    'investment-overflow',
    'dividend-overflow',
  ])
  def test_invalid_properties(self, common_mock, get_normal_user, investments, dividends):
    dummy_expressions = self._get_expressions(investments=Decimal(investments), dividends=Decimal(dividends))
    mock_get_expressions = common_mock(side_effect=DataError('numeric field overflow / out of range'))
    # ------------
    # main routine
    # ------------
    user = get_normal_user

    with pytest.raises(DataError) as ex:
      portfolio = models.PortfolioUser.objects.get(pk=user.pk)
      _ = portfolio.total_investment_amount
    err_msg = str(ex.value).lower()

    assert any([keyword in err_msg for keyword in ['overflow', 'out of range']])

  def test_industry_stat(self, common_mock, mocker, get_normal_user):
    dummy_expressions = self._get_expressions()
    mock_get_expressions = common_mock(return_value=dummy_expressions)
    # ------------
    # main routine
    # ------------
    user = get_normal_user
    portfolio = models.PortfolioUser.objects.get(pk=user.pk)
    _ = list(portfolio.industry_stats)

    assert mock_get_expressions.call_count == 2
    assert mock_get_expressions.mock_calls == [
      mocker.call(relation_prefix='purchased_stocks'),
      mocker.call(relation_prefix=''),
    ]

  def test_empty_portfolio(self, common_mock, get_normal_user):
    empty_expressions = self._get_expressions(0, None, None)
    mock_get_expressions = common_mock(return_value=empty_expressions)
    # ------------
    # main routine
    # ------------
    user = get_normal_user
    portfolio = models.PortfolioUser.objects.get(pk=user.pk)

    assert portfolio is not None
    assert portfolio.purchased_stock_count == 0
    assert portfolio.total_investment_amount == 0
    assert portfolio.total_annual_dividend == 0
    assert portfolio.total_investments is None
    assert portfolio.total_dividends is None
    assert len(list(portfolio.industry_stats)) == 0