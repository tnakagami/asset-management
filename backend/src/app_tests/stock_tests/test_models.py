import pytest
import ast
import json
import re
import urllib.parse
from django.db.models import Q
from django.db.utils import IntegrityError, DataError
from django.core.validators import ValidationError
from django.utils import timezone as djangoTimeZone
from django.contrib.auth import get_user_model
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from stock import models
from app_tests import factories, get_date, BaseTestUtils

UserModel = get_user_model()

class SharedFixtures(BaseTestUtils):
  @pytest.fixture
  def get_judgement_funcs(self):
    def collector(classname, exclude=None):
      ignores = ['id'] if exclude is None else ['id'] + exclude
      return [field.name for field in classname._meta.fields if field.name not in ignores]
    def compare_keys(targets, exacts):
      return (len(targets) == len(exacts)) and all([name == exact_name for name, exact_name in zip(targets, exacts)])
    def compare_values(fields, targets, instance):
      _convertor = lambda val: float(val) if isinstance(val, Decimal) else val
      out = [targets[key] == _convertor(getattr(instance, key)) for key in fields]
      ret = all(out)

      return ret

    return collector, compare_keys, compare_values

  @pytest.fixture(params=[
    ('UTC',        datetime(2010,3,15,20,15,0, tzinfo=timezone.utc), '2010-03-15T20:15:00+00:00'),
    ('Asia/Tokyo', datetime(2010,3,15,20,15,0, tzinfo=timezone.utc), '2010-03-16T05:15:00+09:00'),
  ], ids=lambda xs: '+'.join([xs[0], xs[1].strftime('%Y%m%d-%H:%M:%S'), xs[2]]))
  def pseudo_date(self, request):
    yield request.param

  @pytest.fixture(scope='module')
  def pseudo_stock_data(self, django_db_blocker):
    with django_db_blocker.unblock():
      industries = [
        factories.IndustryFactory(),
        factories.IndustryFactory(),
        factories.IndustryFactory(),
      ]
      localized_industries = [
        factories.LocalizedIndustryFactory(industry=industries[0], name='foo-bar'),
        factories.LocalizedIndustryFactory(industry=industries[1], name='foo'),
        factories.LocalizedIndustryFactory(industry=industries[2], name='hogehoge'),
      ]
      stock_params = [
        {'code': '0010', 'name': 'sampel1', 'industry': 0, 'price': '1200', 'dividend': '15',
          'per':  '0.2', 'pbr': '1.3', 'eps': '1.7', 'bps': '2.3', 'roe': '5.0', 'er': '23.2'},
        {'code': '0012', 'name': 'alpha01', 'industry': 0, 'price': '800', 'dividend': '5',
          'per':  '1.3', 'pbr': '2.5', 'eps': '0.25', 'bps': '1.1', 'roe': '5.3', 'er': '16'},
        {'code': '0033', 'name': 'beta20', 'industry': 1, 'price': '2000', 'dividend': '15.1',
          'per':  '2.2', 'pbr': '4.3', 'eps': '5.3', 'bps': '4.1', 'roe': '7.2', 'er': '12.7'},
        {'code': '005A', 'name': 'kappa88', 'industry': 1, 'price': '1500', 'dividend': '5.2',
          'per':  '5.7', 'pbr': '1.3', 'eps': '7.9', 'bps': '-5.6', 'roe': '2.1', 'er': '8'},
        {'code': '040a', 'name': 'gamma_c', 'industry': 2, 'price': '1000', 'dividend': '9',
          'per':  '1.7', 'pbr': '0.1', 'eps': '3.5', 'bps': '3.7', 'roe': '0.9', 'er': '7.2'},
      ]
      stocks = [
        factories.StockFactory(
          code=kwargs['code'], industry=industries[kwargs['industry']],
          price=Decimal(kwargs['price']), dividend=Decimal(kwargs['dividend']),
          per=Decimal(kwargs['per']), pbr=Decimal(kwargs['pbr']), eps=Decimal(kwargs['eps']),
          bps=Decimal(kwargs['bps']), roe=Decimal(kwargs['roe']), er=Decimal(kwargs['er']), skip_task=False,
        ) for kwargs in stock_params
      ]
      localized_stocks = [
        factories.LocalizedStockFactory(stock=stock, name=kwargs['name'])
        for stock, kwargs in zip(stocks, stock_params)
      ]

    return stocks

class SelectedRangeFixture:
  @pytest.fixture(params=[
    (10, 15, 4, 14, 10),
    (None, 9, 5, 7, 1),
    (25, None, 3, 30, 25),
    (None, None, 17, 30, 1),
  ], ids=[
    'both-date-are-given',
    'from-date-is-empty',
    'to-date-is-empty',
    'both-date-are-empty',
  ], scope='module')
  def get_selected_range(self, request, django_db_blocker):
    from_day, to_day, count, first_day, last_day = request.param
    from_date = get_date((2023, 5, from_day)) if from_day else None
    to_date = get_date((2023, 5, to_day)) if to_day else None
    first_date = get_date((2023, 5, first_day))
    last_date = get_date((2023, 5, last_day))
    # Create records
    with django_db_blocker.unblock():
      user, other = factories.UserFactory.create_batch(2)
      user_pstocks = []
      user_cashes = []

      for _day in [1, 3, 5, 6, 7, 10, 11, 13, 14, 16, 17, 19, 20, 22, 25, 29, 30]:
        target = get_date((2023, 5, _day))
        user_pstocks += [factories.PurchasedStockFactory(user=user, purchase_date=target)]
        user_cashes += [factories.CashFactory(user=user, registered_date=target)]
      for _day in [9, 10, 14, 15, 16, 25, 26]:
        target = get_date((2023, 5, _day))
        _ = factories.PurchasedStockFactory(user=other, purchase_date=target)
        _ = factories.CashFactory(user=other, registered_date=target)
      # Set user's queryset
      user.purchased_stocks.set(models.PurchasedStock.objects.filter(pk__in=self.get_pks(user_pstocks)))
      user.cashes.set(models.Cash.objects.filter(pk__in=self.get_pks(user_cashes)))
    # Create config
    config = {
      'count': count,
      'first_date': first_date,
      'last_date': last_date,
      'from_date': from_date,
      'to_date': to_date,
    }

    return config, user

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
class TestInstanceType(SharedFixtures):
  def test_localized_industry(self):
    localized_industry = factories.LocalizedIndustryFactory()

    assert isinstance(localized_industry, models.LocalizedIndustry)

  def test_localized_stock(self):
    localized_stock = factories.LocalizedStockFactory()

    assert isinstance(localized_stock, models.LocalizedStock)

  def test_industry(self):
    industry = factories.IndustryFactory()

    assert isinstance(industry, models.Industry)

  def test_snapshot(self):
    snapshot = factories.SnapshotFactory()

    assert isinstance(snapshot, models.Snapshot)

  def test_stock(self):
    stock = factories.StockFactory()

    assert isinstance(stock, models.Stock)

  def test_cash(self):
    cash = factories.CashFactory()

    assert isinstance(cash, models.Cash)

  def test_purchased_stock(self):
    purchased_stock = factories.PurchasedStockFactory()

    assert isinstance(purchased_stock, models.PurchasedStock)

class DummyModule:
  def __init__(self, name):
    def updater(**kwargs):
      return 1
    # Define variable and function
    self.stock_records_updater = name
    self.no_decorator_updater = updater
    self.record_updater = models.bind_user_function(updater)

# ================
# Global functions
# ================
@pytest.mark.stock
@pytest.mark.model
class TestGlobalFunction:
  def test_check_bind_function(self):
    @models.bind_user_function
    def target_function():
      return 0

    ret = target_function()

    assert target_function.__name__ == 'as_udf'
    assert ret == 0

  @pytest.mark.parametrize([
    'test_module',
    'checker',
  ], [
    (DummyModule('record_updater'), (lambda ret: ret == 1)),
    (DummyModule('hogehoge'), (lambda ret: ret is None)),
    (DummyModule('no_decorator_updater'), (lambda ret: ret is None)),
    (None, (lambda ret: ret is None)),
  ], ids=[
    'valid-module',
    'no-target-updater-exists',
    'without-decorator',
    'invalid-module',
  ])
  def test_check_get_user_function(self, mocker, test_module, checker):
    callback = models.get_user_function(test_module)
    ret = callback(hoge=1, bar=3)

    assert checker(ret)

  @pytest.mark.parametrize([
    'this_timezone',
    'is_string',
    'strformat',
    'expected',
  ], [
    ('UTC',        False,             None, datetime(2000,1,2,10,0,0, tzinfo=ZoneInfo('UTC'))),
    ('UTC',         True,             None, '2000-01-02T10:00:00+00:00'),
    ('UTC',         True, '%Y-%m-%d %H:%M', '2000-01-02 10:00'),
    ('Asia/Tokyo', False,             None, datetime(2000,1,2,19,0,0, tzinfo=ZoneInfo('Asia/Tokyo'))),
    ('Asia/Tokyo',  True,             None, '2000-01-02T19:00:00+09:00'),
    ('Asia/Tokyo',  True, '%Y-%m-%d %H:%M', '2000-01-02 19:00'),
  ], ids=[
    'to-utc-datetime',
    'to-utc-isoformat',
    'to-utc-string',
    'to-asia-tokyo-datetime',
    'to-asia-tokyo-isoformat',
    'to-asia-tokyo-string',
  ])
  def test_check_convert_timezone(self, settings, this_timezone, is_string, strformat, expected):
    settings.TIME_ZONE = this_timezone
    target = datetime(2000,1,2,10,0,0, tzinfo=timezone.utc)
    output = models.convert_timezone(target, is_string=is_string, strformat=strformat)

    assert output == expected

  def test_check_generate_default_filename(self, mocker, settings):
    settings.TIME_ZONE = 'Asia/Tokyo'
    mocker.patch(
      'stock.models.timezone.now',
      return_value=datetime(2021,7,3,11,7,48,microsecond=123456,tzinfo=timezone.utc),
    )
    expected = '20210703-200748'
    filename = models.generate_default_filename()

    assert filename == expected

  @pytest.mark.parametrize([
    'code',
  ], [
    ('43210', ),
    ('RSTU1', ),
    ('xyzw2', ),
    ('ABxy3', ),
    ('A7890', ),
    ('a3456', ),
    ('', ),
  ], ids=[
    'only-numbers',
    'only-alphabets-of-capital-letter',
    'only-alphabets-of-small-letter',
    'only-alphabets-of-both-capital-and-small-letter',
    'both-numbers-and-capital-letter',
    'both-numbers-and-small-letter',
    'code-is-blank',
  ])
  def test_check_valid_code(self, code):
    try:
      models._validate_code(code)
    except Exception as ex:
      pytest.fail(f'Unexpected Error({code}): {ex}')

  @pytest.mark.parametrize([
    'code',
  ], [
    ('a-123', ),
    ('1.23', ),
    ('2+ab0', ),
    ('3@aB', ),
    ('4#Ab', ),
    ('5$AB', ),
    ('6!23A', ),
    ('7&23b', ),
    ('-1234', ),
    ('1234-', ),
  ], ids=[
    'exists-hyphen',
    'exists-period',
    'exists-plus-mark',
    'exists-at-mark',
    'exists-sharp',
    'exists-dollar-mark',
    'exists-exclamation-mark',
    'exists-ampersand',
    'exists-top-symbol',
    'exists-last-symbol',
  ])
  def test_check_invalid_code(self, code):
    with pytest.raises(ValidationError) as ex:
      models._validate_code(code)
    assert 'either alphabets or numbers' in str(ex.value)

# ===============
# QmodelCondition
# ===============
@pytest.mark.stock
@pytest.mark.model
class TestQmodelCondition:
  @pytest.mark.parametrize([
    'expression',
    'expected',
  ], [
    ('code == "0010"',                         Q(code__exact="0010")),
    ('code != "0010"',                        ~Q(code__exact="0010")),
    ('code in "001"',                          Q(code__contains="001")),
    ('code not in "001"',                     ~Q(code__contains="001")),
    ('price <= 1000',                          Q(price__lte=1000)),
    ('price < 1000',                           Q(price__lt=1000)),
    ('price >= 1000',                          Q(price__gte=1000)),
    ('price > 1000',                           Q(price__gt=1000)),
    ('price > 2 and er < 5',                   Q() & Q(er__lt=5) & (Q(price__gt=2))),
    ('price > 2 or er < 5',                    "(OR: (AND: ), (AND: ('er__lt', 5)), ('price__gt', 2))"),
    ('price > 2.01',                           Q(price__gt=2.01)),
    ('2.01 < price',                           Q(price__gt=2.01)),
    ('2 < er < 3',                             Q(er__lt=3) & Q(er__gt=2)),
    ('2 < er < 3 < bps < 5',                   Q(bps__lt=5) & Q(bps__gt=3) & Q(er__lt=3) & Q(er__gt=2)),
    ('2<er<3',                                 Q(er__lt=3) & Q(er__gt=2)),
    ('(price<5 or name in "001") and 2<er<3',  "(AND: ('er__lt', 3), ('er__gt', 2), (OR: (AND: ), (AND: ('name__contains', '001')), ('price__lt', 5)))"),
  ], ids=[
    'check-eq-expr',
    'check-not-eq-expr',
    'check-include-expr',
    'check-not-include-expr',
    'check-lte-expr',
    'check-lt-expr',
    'check-gte-expr',
    'check-gt-expr',
    'check-and-expr',
    'check-or-expr',
    'check-decimal-point-expr',
    'check-swap-name-and-constant-expr',
    'check-python-specific-expr',
    'check-python-specific-expr-for-multi-version',
    'check-python-specific-without-spaces-expr',
    'check-complex-expr',
  ])
  def test_q_model_condition(self, expression, expected):
    tree = ast.parse(expression, mode='eval')
    visitor = models._AnalyzeAndCreateQmodelCondition()
    visitor.visit(tree)
    estimated = visitor.condition

    assert str(estimated) == str(expected)

  @pytest.mark.parametrize([
    'condition',
  ], [
    ('price < 100',),
    ('100 < price',),
  ], ids=[
    'no-swap-pattern',
    'swap-pattern',
  ])
  def test_no_pairs_for_q_model(self, condition):
    visitor = models._AnalyzeAndCreateQmodelCondition()
    visitor._comp_op_callbacks = {}
    visitor._swap_pairs = {}
    tree = ast.parse(condition, mode='eval')

    with pytest.raises(IndexError):
      visitor.visit(tree)

# ========
# Industry
# ========
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
class TestIndustry(SharedFixtures):
  @pytest.mark.parametrize([
    'name',
    'language_code',
  ], [
    ('same-industry', 'en'),
    ('same-industry', 'ja'),
  ], ids=[
    'language-is-en',
    'language-is-ja',
  ])
  def test_add_same_name(self, name, language_code):
    industry = factories.IndustryFactory()
    _ = models.LocalizedIndustry.objects.create(
      name=name,
      language_code=language_code,
      industry=industry,
    )

    with pytest.raises(IntegrityError) as ex:
      _ = models.LocalizedIndustry.objects.create(
        name=name,
        language_code=language_code,
        industry=industry,
      )
    assert 'unique constraint' in str(ex.value)

  @pytest.mark.parametrize([
    'language_codes',
    'exact_counts',
  ],[
    ([], 0),
    (['en'], 1),
    (['en', 'ja'], 2),
  ], ids=[
    'no-localized-records',
    'only-one-localized-record',
    'two-localized-records',
  ])
  def test_check_locals(self, language_codes, exact_counts):
    exact_name = 'hoge-lang'
    industry = factories.IndustryFactory()
    for language_code in language_codes:
      _ = factories.LocalizedIndustryFactory(
        name=exact_name,
        language_code=language_code,
        industry=industry,
      )
    records = industry.locals.all()

    assert records.count() == exact_counts
    assert all([instance.name == exact_name for instance in records])

  def test_check_get_dict(self):
    instance = factories.IndustryFactory()
    en_lang = factories.LocalizedIndustryFactory(language_code='en', industry=instance)
    ja_lang = factories.LocalizedIndustryFactory(language_code='ja', industry=instance)
    out_dict = instance.get_dict()

    assert all([key in ['names', 'is_defensive'] for key in out_dict.keys()])
    assert out_dict['is_defensive'] == instance.is_defensive
    assert out_dict['names'] == {'en': en_lang.name, 'ja': ja_lang.name}

  @pytest.mark.parametrize([
    'language_code',
    'name',
    'exact_name',
  ], [
    ('en', 'hogehoge-en', 'hogehoge-en'),
    ('fr', 'hogehoge-fr', ''),
  ], ids=[
    'exists-target-language-code-instance',
    'does-not-exist-target-language-code-instance',
  ])
  def test_check_str_function(self, mocker, language_code, name, exact_name):
    mocker.patch('stock.models.get_language', return_value='en')
    instance = factories.IndustryFactory()
    _ = factories.LocalizedIndustryFactory(
      name=name,
      language_code=language_code,
      industry=instance,
    )
    out = str(instance)

    assert out == exact_name

# =====
# Stock
# =====
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
class TestStock(SharedFixtures):
  @pytest.mark.parametrize([
    'name',
    'language_code',
  ], [
    ('same-stock', 'en'),
    ('same-stock', 'ja'),
  ], ids=[
    'language-is-en',
    'language-is-ja',
  ])
  def test_add_same_name(self, name, language_code):
    stock = factories.StockFactory()
    _ = models.LocalizedStock.objects.create(
      name=name,
      language_code=language_code,
      stock=stock,
    )

    with pytest.raises(IntegrityError) as ex:
      _ = models.LocalizedStock.objects.create(
        name=name,
        language_code=language_code,
        stock=stock,
      )
    assert 'unique constraint' in str(ex.value)

  @pytest.mark.parametrize([
    'language_codes',
    'exact_counts',
  ],[
    ([], 0),
    (['en'], 1),
    (['en', 'ja'], 2),
  ], ids=[
    'no-localized-records',
    'only-one-localized-record',
    'two-localized-records',
  ])
  def test_check_locals(self, language_codes, exact_counts):
    exact_name = 'hoge-lang'
    stock = factories.StockFactory()
    for language_code in language_codes:
      _ = factories.LocalizedStockFactory(
        name=exact_name,
        language_code=language_code,
        stock=stock,
      )
    records = stock.locals.all()

    assert records.count() == exact_counts
    assert all([instance.name == exact_name for instance in records])

  @pytest.mark.parametrize([
    'code',
  ], [
    ('4321A', ),
    ('abcd4', ),
    ('RSTU3', ),
    ('12abZ', ),
    ('12ABz', ),
  ], ids=[
    'only-numbers',
    'only-small-letters',
    'only-capital-letters',
    'both-numbers-and-small-letters',
    'both-numbers-and-capital-letters',
  ])
  def test_add_same_code(self, code):
    _ = factories.StockFactory(code=code)

    with pytest.raises(ValidationError) as ex:
      _ = factories.StockFactory(code=code)
    assert 'Stock code already exists' in str(ex.value)

  @pytest.mark.parametrize([
    'options',
  ], [
    ({}, ),
    ({'price': 0}, ),
    ({'price': 99999999.99}, ),
    ({'dividend': 0}, ),
    ({'dividend': 99999.99}, ),
    ({'per': 0}, ),
    ({'per': 99999.99}, ),
    ({'pbr': 0}, ),
    ({'pbr': 99999.99}, ),
    ({'eps': -99999.99}, ),
    ({'eps':  99999.99}, ),
    ({'bps': -99999.99}, ),
    ({'bps':  99999.99}, ),
    ({'roe':  -9999.99}, ),
    ({'roe':   9999.99}, ),
    ({'er':    -999.99}, ),
    ({'er':     999.99}, ),
  ], ids=[
    'valid-values',
    'min-value-of-price',
    'max-value-of-price',
    'min-value-of-dividend',
    'max-value-of-dividend',
    'min-value-of-per',
    'max-value-of-per',
    'min-value-of-pbr',
    'max-value-of-pbr',
    'min-value-of-eps',
    'max-value-of-eps',
    'min-value-of-bps',
    'max-value-of-bps',
    'min-value-of-roe',
    'max-value-of-roe',
    'min-value-of-er',
    'max-value-of-er',
  ])
  def test_check_valid_inputs(self, options):
    kwargs = {
      'price':    Decimal('1.23'),
      'dividend': Decimal('12.0'),
      'per':      Decimal('1.07'),
      'pbr':      Decimal('2.0'),
      'eps':      Decimal('1.12'),
      'bps':      Decimal('2.33'),
      'roe':      Decimal('5.41'),
      'er':       Decimal('13.41'),
    }
    kwargs.update(options)

    try:
      _ = models.Stock.objects.create(
        code='12A3C4',
        industry=factories.IndustryFactory(),
        **kwargs,
      )
    except ValidationError as ex:
      pytest.fail(f'Unexpected Error: {ex}')

  @pytest.mark.parametrize([
    'options',
    'err_idx',
    'digit',
  ], [
    ({'price':          -0.01}, 0, 10), ({'price':    78.991}, 1, 2), ({'price':    100000000.00}, 2, 8),
    ({'dividend':       -0.01}, 0,  7), ({'dividend': 78.991}, 1, 2), ({'dividend':   1000000.00}, 2, 5),
    ({'per':            -0.01}, 0,  7), ({'per':      78.991}, 1, 2), ({'per':        1000000.00}, 2, 5),
    ({'pbr':            -0.01}, 0,  7), ({'pbr':      78.991}, 1, 2), ({'pbr':        1000000.00}, 2, 5),
    ({'eps':      -1000000.00}, 2,  5), ({'eps':      78.991}, 1, 2), ({'eps':        1000000.00}, 2, 5),
    ({'bps':      -1000000.00}, 2,  5), ({'bps':      78.991}, 1, 2), ({'bps':        1000000.00}, 2, 5),
    ({'roe':       -100000.00}, 2,  4), ({'roe':      78.991}, 1, 2), ({'roe':         100000.00}, 2, 4),
    ({'er':         -10000.00}, 2,  3), ({'er':       78.991}, 1, 2), ({'er':           10000.00}, 2, 3),
  ], ids=[
    'negative-price',    'invalid-decimal-part-of-price',    'invalid-max-digits-of-price',
    'negative-dividend', 'invalid-decimal-part-of-dividend', 'invalid-max-digits-of-dividend',
    'negative-per',      'invalid-decimal-part-of-per',      'invalid-max-digits-of-per',
    'negative-pbr',      'invalid-decimal-part-of-pbr',      'invalid-max-digits-of-pbr',
    'negative-eps',      'invalid-decimal-part-of-eps',      'invalid-max-digits-of-eps',
    'negative-bps',      'invalid-decimal-part-of-bps',      'invalid-max-digits-of-bps',
    'negative-roe',      'invalid-decimal-part-of-roe',      'invalid-max-digits-of-roe',
    'negative-er',       'invalid-decimal-part-of-er',       'invalid-max-digits-of-er',
  ])
  def test_check_invalid_inputs(self, options, err_idx, digit):
    err_types = [
      'digits in total',
      'decimal places',
      'digits before the decimal point',
    ]
    _type = err_types[err_idx]
    err_msg = f'Ensure that there are no more than {digit} {_type}'

    with pytest.raises(ValidationError) as ex:
      _ = models.Stock.objects.create(
        code='1234',
        industry=factories.IndustryFactory(),
        **options,
      )
    assert err_msg in str(ex.value)

  def test_default_select_targets_queryset(self, mocker):
    stocks = [
      *factories.StockFactory.create_batch(3, skip_task=True),
      *factories.StockFactory.create_batch(4, skip_task=False)
    ]
    queryset = models.Stock.objects.filter(pk__in=self.get_pks(stocks))
    mocker.patch('stock.models.StockManager.get_queryset', return_value=queryset)
    all_counts = queryset.count()
    specific = models.Stock.objects.select_targets().count()

    assert all_counts == 7
    assert specific == 4

  @pytest.mark.parametrize([
    'expression',
    'indices',
  ], [
    ('code in "001"', [0, 1]),
    ('name == "gamma_c"', [4]),
    ('industry_name not in "foo"', [4]),
    ('price <= 1000', [1, 4]),
    ('dividend > 6', [0, 2, 4]),
    ('1.1 < per < 2.5', [1, 2, 4]),
    ('pbr > 10', []),
    ('eps == 0.25', [1]),
    ('bps <= 0', [3]),
    ('roe < 2 or 5 < roe', [1, 2, 4]),
    ('8 <= er and er <= 16', [1, 2, 3]),
    ('code in "1" and price < 1000 or name in "_" or industry_name == "foo" or price > 1000', [0,1,2,3,4]),
  ], ids=[
    'based-on-code',
    'based-on-name',
    'based-on-industry',
    'based-on-price',
    'based-on-dividend',
    'based-on-per',
    'based-on-pbr',
    'based-on-eps',
    'based-on-bps',
    'based-on-roe',
    'based-on-er',
    'complex-expression-by-using-several-columns',
  ])
  def test_select_targets_with_tree(self, mocker, pseudo_stock_data, expression, indices):
    stocks = pseudo_stock_data
    queryset = models.Stock.objects.filter(pk__in=self.get_pks(stocks))
    mocker.patch('stock.models.StockManager.get_queryset', return_value=queryset)
    tree = ast.parse(expression, mode='eval')
    qs = models.Stock.objects.select_targets(tree=tree).order_by('pk')
    expected = [stocks[idx].pk for idx in indices]

    assert qs.count() == len(expected)
    assert all([record.pk == pk for record, pk in zip(qs, expected)])

  def test_check_get_dict(self, get_judgement_funcs):
    collector, compare_keys, compare_values = get_judgement_funcs
    instance = factories.StockFactory()
    en_lang = factories.LocalizedStockFactory(language_code='en', stock=instance)
    ja_lang = factories.LocalizedStockFactory(language_code='ja', stock=instance)
    out_dict = instance.get_dict()
    fields = collector(models.Stock, exclude=['industry', 'skip_task'])
    industry = out_dict.pop('industry', None)
    skip_task = out_dict.pop('skip_task', None)
    names = out_dict.pop('names', None)

    assert industry is not None
    assert skip_task is None
    assert names == {'en': en_lang.name, 'ja': ja_lang.name}
    assert compare_keys(list(out_dict.keys()), fields)
    assert compare_values(fields, out_dict, instance)

  @pytest.mark.parametrize([
    'language_code',
    'name',
    'exact_name',
  ], [
    ('en', 'hogehoge-en', 'hogehoge-en'),
    ('fr', 'hogehoge-fr', ''),
  ], ids=[
    'exists-target-language-code-instance',
    'does-not-exist-target-language-code-instance',
  ])
  def test_check_str_function(self, mocker, language_code, name, exact_name):
    mocker.patch('stock.models.get_language', return_value='en')
    code = '102A34'
    instance = factories.StockFactory(code=code)
    _ = factories.LocalizedStockFactory(
      name=name,
      language_code=language_code,
      stock=instance,
    )
    out = str(instance)
    expected = f'{exact_name}({code})'

    assert out == expected

  @pytest.mark.parametrize([
    'filename',
    'condition',
    'ordering',
    'total',
    'start_idx',
    'end_idx',
  ], [
    ('hoge', '', 'code', 5, 0, -1),
    ('', 'price >= 1200', '-price', 3, 2, 0),
    ('foo', '1.3 <= pbr <= 4.5', 'pbr,-per', 4, 3, 2),
    ('日本語', 'bps < 0', 'er', 1, 3, 3),
  ], ids=[
    'no-condition',
    'empty-filename',
    'same-values-exist',
    'use-multi-byte-string-in-filename',
  ])
  def test_get_response_kwargs(self, mocker, pseudo_stock_data, filename, condition, ordering, total, start_idx, end_idx):
    default_fname = '20010917-213456'
    stocks = pseudo_stock_data
    queryset = models.Stock.objects.filter(pk__in=self.get_pks(stocks))
    mocker.patch('stock.models.StockManager.get_queryset', return_value=queryset)
    mocker.patch('stock.models.generate_default_filename', return_value=default_fname)
    tree = ast.parse(condition, mode='eval') if condition else None
    # Call target function
    kwargs = models.Stock.get_response_kwargs(filename, tree, ordering.split(','))
    # Create expected values
    first_obj = stocks[start_idx]
    last_obj = stocks[end_idx]
    _tmp_name = filename if filename else default_fname
    expected_name = urllib.parse.quote(_tmp_name.encode('utf-8'))
    expected_header = [
      'Stock code', 'Stock name', 'Stock industry', 'Stock price', 'Dividend', 'Dividend yield',
      'Price Earnings Ratio (PER)', 'Price Book-value Ratio (PBR)', 'PER x PBR',
      'Earnings Per Share (EPS)', 'Book value Per Share (BPS)', 'Return On Equity (ROE)',
      'Equity Ratio (ER)',
    ]
    # Get estimated values
    rows = list(kwargs['rows'])
    estimated_first = rows[0]
    estimated_last = rows[-1]

    assert len(rows) == total
    assert estimated_first[0] == first_obj.code
    assert estimated_first[1] == first_obj.get_name()
    assert estimated_last[0] == last_obj.code
    assert estimated_last[1] == last_obj.get_name()
    assert all([str(est) == exact for est, exact in zip(kwargs['header'], expected_header)])
    assert kwargs['filename'] == f'stock-{expected_name}.csv'

  def test_get_response_kwargs_with_no_data(self):
    kwargs = models.Stock.get_response_kwargs('', None, ['code'])
    queryset = models.Stock.objects.select_targets().order_by('code')

    assert len(list(kwargs['rows'])) == len(queryset)

  def test_check_get_choices_as_list(self, mocker):
    stocks = [
      factories.StockFactory(code='0101'),
      factories.StockFactory(code='0202'),
    ]
    localized_stocks = [
      factories.LocalizedStockFactory(name='stock1-en', language_code='en', stock=stocks[0]),
      factories.LocalizedStockFactory(name='stock1-ja', language_code='ja', stock=stocks[0]),
      factories.LocalizedStockFactory(name='stock2-en', language_code='en', stock=stocks[1]),
      factories.LocalizedStockFactory(name='stock2-ja', language_code='ja', stock=stocks[1]),
    ]
    queryset = models.Stock.objects.filter(pk__in=self.get_pks(stocks))
    mocker.patch('stock.models.get_language', return_value='en')
    mocker.patch('stock.models.StockManager.get_queryset', return_value=queryset)
    data = models.Stock.get_choices_as_list()

    assert all([
      all([key in item.keys() for key in ['pk', 'name', 'code']]) for item in data
    ])
    assert len(stocks) == len(data)
    assert all([
      all([stock.pk == item['pk'], stock.code == item['code'], stock.get_name() == item['name']])
      for stock, item in zip(stocks, data)
    ])

# ====
# Cash
# ====
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
class TestCash(SharedFixtures, SelectedRangeFixture):
  @pytest.mark.parametrize([
    'balance',
  ], [
    (0, ),
    (1, ),
    (2147483647, ),
  ], ids=[
    'is-zero',
    'is-one',
    'is-max',
  ])
  def test_check_valid_balance(self, get_user, balance):
    user = get_user

    try:
      _ = models.Cash.objects.create(
        user=user,
        balance=balance,
        registered_date=djangoTimeZone.now(),
      )
    except IntegrityError as ex:
      pytest.fail(f'Unexpected Error: {ex}')

  @pytest.mark.parametrize([
    'balance',
    'exception_type',
    'err_msg',
  ], [
    (-1, IntegrityError, 'violates check constraint'),
    (2147483647 + 1, DataError, 'integer out of range'),
  ], ids=[
    'is-negative',
    'is-overflow',
  ])
  def test_check_invalid_balance(self, get_user, balance, exception_type, err_msg):
    user = get_user

    with pytest.raises(exception_type) as ex:
      _ = models.Cash.objects.create(
        user=user,
        balance=balance,
        registered_date=djangoTimeZone.now(),
      )
    assert err_msg in str(ex.value)

  def test_check_get_dict(self, get_judgement_funcs):
    collector, compare_keys, compare_values = get_judgement_funcs
    target = get_date((2022, 3, 4))
    instance = factories.CashFactory(
      registered_date=target,
    )
    out_dict = instance.get_dict()
    fields = collector(models.Cash, exclude=['user', 'registered_date'])
    _registered_date = out_dict.pop('registered_date', None)

    assert _registered_date is not None
    assert compare_keys(list(out_dict.keys()), fields)
    assert compare_values(fields, out_dict, instance)
    assert _registered_date == models.convert_timezone(target, is_string=True)

  def test_check_str_function(self, settings, pseudo_date, get_user):
    this_timezone, target_date, exact_date = pseudo_date
    settings.TIME_ZONE = this_timezone
    instance = factories.CashFactory(
      user=get_user,
      balance=12345,
      registered_date=target_date,
    )
    out = str(instance)
    expected = f'{instance.balance}({exact_date})'

    assert out == expected

  def test_selected_range_queryset(self, get_selected_range):
    config, user = get_selected_range
    # Collect relevant queryset (order: '-registered_date')
    queryset = user.cashes.selected_range(config['from_date'], config['to_date'])
    _first = queryset.first()
    _last = queryset.last()

    assert len(queryset) == config['count']
    assert all([record.user == user for record in queryset])
    assert _first.registered_date == config['first_date']
    assert _last.registered_date == config['last_date']

# ==============
# PurchasedStock
# ==============
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
class TestPurchasedStock(SharedFixtures, SelectedRangeFixture):
  @pytest.mark.parametrize([
    'options',
  ], [
    ({}, ),
    ({'price': 0}, ),
    ({'price': 999999999.99}, ),
    ({'count': 0}, ),
    ({'count': 2147483647}, ),
  ], ids=[
    'valid-values',
    'min-value-of-price',
    'max-value-of-price',
    'min-value-of-count',
    'max-value-of-count',
  ])
  def test_check_valid_inputs(self, options, get_user):
    kwargs = {
      'price': Decimal('1.23'),
      'count': 100,
    }
    kwargs.update(options)

    try:
      _ = models.PurchasedStock.objects.create(
        user=get_user,
        stock=factories.StockFactory(),
        purchase_date=get_date((1999, 1, 2)),
        **kwargs,
      )
    except ValidationError as ex:
      pytest.fail(f'Unexpected Error: {ex}')

  @pytest.mark.parametrize([
    'options',
    'exception_type',
    'err_msg',
  ], [
    ({'price':          -0.01}, ValidationError, '11 digits in total'),
    ({'price':         12.991}, ValidationError, '2 decimal places'),
    ({'price':  1000000000.00}, ValidationError, '9 digits before the decimal point'),
    ({'count':             -1}, ValidationError, 'greater than or equal to 0'),
    ({'count': 2147483647 + 1}, ValidationError, 'less than or equal to 2147483647'),
  ], ids=[
    'negative-purchased-price',
    'invalid-decimal-part-of-purchased-price',
    'invalid-max-digits-of-purchased-price',
    'is-negative-count',
    'is-overflow-count',
  ])
  def test_check_invalid_inputs(self, get_user, options, exception_type, err_msg):
    kwargs = {
      'price': Decimal('1.23'),
      'count': 100,
    }
    kwargs.update(options)

    with pytest.raises(exception_type) as ex:
      _ = models.PurchasedStock.objects.create(
        user=get_user,
        stock=factories.StockFactory(),
        purchase_date=get_date((1999, 1, 2)),
        **kwargs,
      )
    assert err_msg in str(ex.value)

  @pytest.mark.parametrize([
    'sold_out',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'has-been-sold',
    'has-not-been-sold',
  ])
  def test_check_get_dict(self, get_judgement_funcs, sold_out):
    collector, compare_keys, compare_values = get_judgement_funcs
    target = get_date((2022, 3, 4))
    instance = factories.PurchasedStockFactory(
      purchase_date=target,
      has_been_sold=sold_out,
    )
    out_dict = instance.get_dict()
    fields = collector(models.PurchasedStock, exclude=['user', 'stock', 'purchase_date', 'has_been_sold'])
    _stock = out_dict.pop('stock', None)
    _purchase_date = out_dict.pop('purchase_date', None)

    assert _stock is not None
    assert _purchase_date is not None
    assert compare_keys(list(out_dict.keys()), fields)
    assert compare_values(fields, out_dict, instance)
    assert _purchase_date == models.convert_timezone(target, is_string=True)

  def test_check_str_function(self, mocker, settings, pseudo_date, get_user):
    mocker.patch('stock.models.get_language', return_value='en')
    this_timezone, target_date, exact_date = pseudo_date
    settings.TIME_ZONE = this_timezone
    stock = factories.StockFactory()
    instance = factories.PurchasedStockFactory(
      user=get_user,
      stock=stock,
      purchase_date=target_date,
      count=100,
    )
    _ = factories.LocalizedStockFactory(language_code='en', stock=stock)
    _ = factories.LocalizedStockFactory(language_code='ja', stock=stock)
    out = str(instance)
    expected = f'{instance.stock.get_name()}({exact_date},{instance.count})'

    assert out == expected

  def test_older_queryset(self):
    user, other = factories.UserFactory.create_batch(2)
    # 24/3/20, 24/3/19, 24/3/18
    exact0318 = get_date((2024, 3, 18))
    exact0319 = get_date((2024, 3, 19))
    exact0320 = get_date((2024, 3, 20))
    _ = factories.PurchasedStockFactory(user=user, purchase_date=exact0320)
    _ = factories.PurchasedStockFactory(user=user, purchase_date=exact0319)
    _ = factories.PurchasedStockFactory(user=user, purchase_date=exact0318)
    _ = factories.PurchasedStockFactory(user=other, purchase_date=exact0319)
    # Collect relevant queryset (order: 'purchase_date')
    queryset = user.purchased_stocks.older()

    assert len(queryset) == 3
    assert all([record.user == user for record in queryset])
    assert queryset[0].purchase_date == exact0318
    assert queryset[1].purchase_date == exact0319
    assert queryset[2].purchase_date == exact0320

  def test_selected_range_queryset(self, get_selected_range):
    config, user = get_selected_range
    # Collect relevant queryset (order: '-purchase_date')
    queryset = user.purchased_stocks.selected_range(config['from_date'], config['to_date'])
    _first = queryset.first()
    _last = queryset.last()

    assert len(queryset) == config['count']
    assert all([record.user == user for record in queryset])
    assert _first.purchase_date == config['first_date']
    assert _last.purchase_date == config['last_date']

  def test_ignore_sold_stocks(self, get_user):
    user = get_user
    pstocks = [
      factories.PurchasedStockFactory(user=user, has_been_sold=True),
      factories.PurchasedStockFactory(user=user, has_been_sold=False),
      factories.PurchasedStockFactory(user=user, has_been_sold=True),
    ]
    queryset = user.purchased_stocks.selected_range()
    the1st_instance = queryset.first()

    assert queryset.count() == 1
    assert the1st_instance.pk == pstocks[1].pk

# ==============
# SnapshotRecord
# ==============
@pytest.mark.stock
@pytest.mark.model
class TestSnapshotRecord(SharedFixtures):
  @pytest.fixture
  def get_default_record(self):
    params = {
      'code': '7531', 'price': 123.0, 'dividend': 3.0, 'per': 2.0,
      'pbr': 1.0, 'eps': 0.2, 'bps': 0.3, 'roe': 0.1, 'er': 3.0,
    }
    instance = models._SnapshotRecord(**params)

    return instance

  def test_check_instanec(self, get_default_record):
    instance = get_default_record

    assert isinstance(instance, models._SnapshotRecord)

  @pytest.mark.parametrize([
    'is_defensive',
    'expected_trend',
  ], [
    (True, 'Defensive'),
    (False, 'Economically sensitive'),
  ], ids=[
    'is-defensive',
    'is-not-defensive',
  ])
  def test_check_get_trend(self, get_default_record, is_defensive, expected_trend):
    instance = get_default_record
    trend = instance._get_trend(is_defensive)

    assert trend == expected_trend

  @pytest.mark.parametrize([
    'dict_item',
    'lang',
    'expected',
  ], [
    ({'name': 'hoge'}, 'en', 'hoge'),
    ({'name':  'foo'}, 'ge', 'foo'),
    ({'names': {'en': 'en-hoge', 'ge': 'ge-foo'}}, 'en', 'en-hoge'),
    ({'names': {'en': 'en-hoge', 'ge': 'ge-foo'}}, 'ge', 'ge-foo'),
  ], ids=[
    'includes-name-in-English',
    'includes-name-in-German',
    'includes-names-in-English',
    'includes-names-in-German',
  ])
  def test_check_get_name(self, mocker, get_default_record, dict_item, lang, expected):
    mocker.patch('stock.models.get_language', return_value=lang)
    instance = get_default_record
    name = instance._get_name(dict_item)

    assert name == expected

  def test_check_set_stock_name(self, mocker, get_default_record):
    expected = 'hoge'
    mocker.patch('stock.models._SnapshotRecord._get_name', return_value=expected)
    instance = get_default_record
    instance.name = '-'
    instance.set_name({})

    assert instance.name == expected

  def test_check_set_industry(self, mocker, get_default_record):
    expected_name = 'hoge'
    expected_trend = 'Defensive'
    mocker.patch('stock.models._SnapshotRecord._get_name', return_value=expected_name)
    mocker.patch('stock.models._SnapshotRecord._get_trend', return_value=expected_trend)
    instance = get_default_record
    instance.industry = '-'
    instance.trend = '-'
    instance.set_industry({'is_defensive': False})

    assert instance.industry == expected_name
    assert instance.trend == expected_trend

  def test_check_add_count(self, get_default_record):
    instance = get_default_record
    instance.count = 3
    instance.add_count(2)

    assert instance.count == 5

  @pytest.mark.stock
  @pytest.mark.model
  def test_check_add_value(self, get_default_record):
    instance = get_default_record
    instance.purchased_value = 5
    instance.add_value(100, 2)

    assert instance.purchased_value == 205

  @pytest.mark.parametrize([
    'count',
    'expected_real_dividend',
  ], [
    (200, 4800.0),
    (0, 0.0),
  ], ids=[
    'stock-exists',
    'stock-does-not-exist',
  ])
  def test_check_real_div_value(self, get_default_record, count, expected_real_dividend):
    instance = get_default_record
    instance.dividend = 24.0
    instance.count = count

    assert abs(instance.real_div - expected_real_dividend) < 1e-6

  @pytest.mark.parametrize([
    'purchased_value',
    'expected',
  ], [
    (68000.0, 110 / 34.0),
    (0.0, 0.0),
  ], ids=[
    'pval-is-more-than-zero',
    'pval-is-zero',
  ])
  def test_check_div_yield_value(self, get_default_record, purchased_value, expected):
    instance = get_default_record
    instance.purchased_value = purchased_value
    instance.dividend = 11.0
    instance.count = 200

    assert abs(instance.div_yield - expected) < 1e-6

  @pytest.mark.parametrize([
    'count',
    'expected_diff',
  ], [
    (200, -10000.0),
    (0, 0.0),
  ], ids=[
    'exists-purchased-history',
    'is-cash',
  ])
  def test_check_diff_value(self, get_default_record, count, expected_diff):
    instance = get_default_record
    instance.purchased_value = 190000.0
    instance.price = 900.0
    instance.count = count

    assert abs(instance.diff - expected_diff) < 1e-6

  @pytest.mark.parametrize([
    'price',
    'expected_stock_yield',
  ], [
    (1000, 4.12),
    (0, 0.0),
  ], ids=[
    'valid-stock-price',
    'invalid-stock-price',
  ])
  def test_check_stock_yield_value(self, get_default_record, price, expected_stock_yield):
    instance = get_default_record
    instance.dividend = 41.2
    instance.price = price

    assert abs(instance.stock_yield - expected_stock_yield) < 1e-6

  def test_check_get_record(self):
    instance = models._SnapshotRecord(
      code='5384',
      name='hoge2',
      industry='foo3',
      trend='Defensive',
      dividend=2.0,
      purchased_value=2000.0,
      count=2,
      price=1100.0,
      per=0.164,
      pbr=1.223,
      eps=4.235,
      bps=0.147,
      roe=10.1,
      er=11.22,
    )
    expected = [
      '5384',      # Code
      'hoge2',     # Name
      'foo3',      # industry
      'Defensive', # trend
      '4.00',      # dividend * count
      '0.20',      # div_yield
      '2000.00',   # purchased_value
      '2',         # count
      '200.00',    # diff
      '1100.00',   # price
      '0.16',      # per
      '1.22',      # pbr
      '4.24',      # eps
      '0.15',      # bps
      '10.10',     # roe
      '11.22',     # er
    ]
    record = instance.get_record()

    assert all([est == exact for est, exact in zip(record, expected)])

  def test_check_get_header(self, get_default_record):
    instance = get_default_record
    expected = [
      'Stock code',
      'Name',
      'Stock industry',
      'Economic trend',
      'Dividend',
      'Dividend yield',
      'Purchased value',
      'Number of stocks',
      'Diff',
      'Stock price',
      'Price Earnings Ratio (PER)',
      'Price Book-value Ratio (PBR)',
      'Earnings Per Share (EPS)',
      'Book value Per Share (BPS)',
      'Return On Equity (ROE)',
      'Equity Ratio (ER)',
    ]
    header = instance.get_header()

    assert all([est == exact for est, exact in zip(header, expected)])

# ========
# Snapshot
# ========
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
class TestSnapshot(SharedFixtures):
  def test_check_that_json_field_is_empty(self, get_user):
    instance = models.Snapshot.objects.create(
      user=get_user,
      title='Detail field is empty',
    )
    out_dict = json.loads(instance.detail)

    assert all(key in out_dict.keys() for key in ['cash', 'purchased_stocks'])
    assert len(out_dict['cash']) == 0
    assert len(out_dict['purchased_stocks']) == 0

  @pytest.mark.parametrize([
    'balances',
    'months_days',
    'exact_idx',
  ], [
    ([123], [(2,10)], 0),
    ([123, 456], [(1,30), (2,9)], 1),
    ([123, 789, 456], [(2,1), (2,15), (1,30)], 1),
  ], ids=[
    'only-one-cash-is-recorded',
    'multi-cashes-are-recorded',
    'newest-record-is-mixed',
  ])
  def test_check_that_cashes_exist(self, get_user, balances, months_days, exact_idx):
    user = get_user
    reg_dates = []

    for balance, month_day in zip(balances, months_days):
      target = get_date((2024, *month_day))
      _ = factories.CashFactory(
        user=user,
        balance=balance,
        registered_date=target
      )
      reg_dates += [target]

    instance = models.Snapshot.objects.create(
      user=user,
      title="User's cashes exist",
    )
    out_dict = json.loads(instance.detail)
    # Create exact data
    expected_balance = balances[exact_idx]
    expected_date = models.convert_timezone(reg_dates[exact_idx], is_string=True)

    assert all(key in out_dict.keys() for key in ['cash', 'purchased_stocks'])
    assert len(out_dict['cash']) == 2
    assert len(out_dict['purchased_stocks']) == 0
    assert out_dict['cash']['balance'] == expected_balance
    assert out_dict['cash']['registered_date'] == expected_date

  @pytest.mark.parametrize([
    'number_of_purchased_stocks',
  ], [
    (1, ),
    (3, ),
  ], ids=[
    'only-one-purchased_stock-exists',
    'multi-purchased_stocks-exist',
  ])
  def test_check_that_purchased_stocks_exist(self, get_user, number_of_purchased_stocks):
    user = get_user
    stocks = factories.StockFactory.create_batch(number_of_purchased_stocks)
    purchased_stocks = sorted(
      [factories.PurchasedStockFactory(stock=stock, user=user) for stock in stocks],
      key=lambda obj: obj.purchase_date,
      reverse=True,
    )
    for stock in stocks:
      factories.LocalizedStockFactory(name='stock-ja', language_code='ja', stock=stock)
      factories.LocalizedStockFactory(name='stock-en', language_code='en', stock=stock)
    instance = models.Snapshot.objects.create(
      user=user,
      title="User's purchsed stocks exist",
    )
    out_dict = json.loads(instance.detail)

    assert all(key in out_dict.keys() for key in ['cash', 'purchased_stocks'])
    assert len(out_dict['cash']) == 0
    assert len(out_dict['purchased_stocks']) == number_of_purchased_stocks
    assert all([
      {'en': 'stock-en', 'ja': 'stock-ja'} == extracted['stock']['names']
      for extracted in out_dict['purchased_stocks']
    ])
    assert all([
      all([
        extracted['price'] == float(exact_val.price),
        extracted['purchase_date'] == models.convert_timezone(exact_val.purchase_date, is_string=True),
        extracted['count'] == exact_val.count,
      ])
      for extracted, exact_val in zip(out_dict['purchased_stocks'], purchased_stocks)
    ])

  def test_check_general_pattern(self, get_user):
    user = get_user
    cashes = factories.CashFactory.create_batch(4, user=user)
    stocks = factories.StockFactory.create_batch(4)
    purchased_stocks = sorted(
      [factories.PurchasedStockFactory(stock=stock, user=user) for stock in stocks],
      key=lambda obj: obj.purchase_date,
      reverse=True,
    )
    for stock in stocks:
      factories.LocalizedStockFactory(name='stock-ja', language_code='ja', stock=stock)
      factories.LocalizedStockFactory(name='stock-en', language_code='en', stock=stock)
    instance = models.Snapshot.objects.create(
      user=user,
      title="It's general pattern",
    )
    out_dict = json.loads(instance.detail)
    # Create expected data
    exact_cash_idx, cash_date = 0, cashes[0].registered_date
    for idx, _cash in enumerate(cashes[1:], 1):
      if cash_date < _cash.registered_date:
        exact_cash_idx, cash_date = idx, _cash.registered_date

    assert all(key in out_dict.keys() for key in ['cash', 'purchased_stocks'])
    assert len(out_dict['cash']) == 2
    assert len(out_dict['purchased_stocks']) == 4
    assert out_dict['cash']['balance'] == cashes[exact_cash_idx].balance
    assert out_dict['cash']['registered_date'] == models.convert_timezone(cashes[exact_cash_idx].registered_date, is_string=True)
    assert all([
      {'en': 'stock-en', 'ja': 'stock-ja'} == extracted['stock']['names']
      for extracted in out_dict['purchased_stocks']
    ])
    assert all([
      all([
        extracted['purchase_date'] == models.convert_timezone(exact_val.purchase_date, is_string=True),
        extracted['count'] == exact_val.count,
      ])
      for extracted, exact_val in zip(out_dict['purchased_stocks'], purchased_stocks)
    ])

  def test_check_str_function(self, settings, pseudo_date, get_user):
    this_timezone, target_date, exact_date = pseudo_date
    settings.TIME_ZONE = this_timezone
    instance = factories.SnapshotFactory(
      user=get_user,
      title='sample-title',
      detail='{"key1":3,"key2":"a","key3":4}',
      created_at=target_date,
    )
    out = str(instance)
    expected = f'{instance.title}({exact_date})'

    assert out == expected

  def test_check_save_method(self, get_user):
    user = get_user
    _ = factories.CashFactory.create_batch(2, user=user)
    _ = factories.PurchasedStockFactory.create_batch(3, user=user)
    instance = models.Snapshot.objects.create(
      user=user,
      title='save instance for the 1st time',
    )
    # Update details
    detail_dict = {
      'cash': {},
      'purchased_stocks': {
        'stock': {
          'names': {'en': 'hogehoge-en'},
        },
        'purchase_date': None,
      },
    }
    instance.detail = json.dumps(detail_dict)
    instance.title = 'updated the record'
    instance.save()
    # Get updated instance
    estimated = models.Snapshot.objects.get(pk=instance.pk)
    out_dict = json.loads(estimated.detail)

    assert estimated.title == instance.title
    assert len(out_dict['cash']) == 0
    assert out_dict['purchased_stocks']['stock']['names'] == {'en': 'hogehoge-en'}
    assert out_dict['purchased_stocks']['purchase_date'] is None

  @pytest.mark.parametrize([
    'config',
  ], [
    ({'start':   10, 'end':   15, 'num_pstock': 0, 'exact_start': 10, 'exact_end': 15}, ), # same as definition date
    ({'start': None, 'end': None, 'num_pstock': 0, 'exact_start': 25, 'exact_end': 25}, ), # same as timezone.now
    ({'start': None, 'end':   15, 'num_pstock': 0, 'exact_start': 15, 'exact_end': 15}, ), # same as end_date
    ({'start': None, 'end':   15, 'num_pstock': 2, 'exact_start': 10, 'exact_end': 15}, ), # same as oldest date of purchased stock record
    ({'start':   12, 'end': None, 'num_pstock': 0, 'exact_start': 12, 'exact_end': 25}, ), # same as definition date
  ], ids=[
    'both-dates-exist',
    'both-dates-donot-exist',
    'start-date-and-purchased-stock-are-none',
    'start-date-is-none',
    'end-date-is-none',
  ])
  def test_range_patterns(self, get_user, mocker, config):
    # Calculate exact value
    exact_start_date = get_date((2024, 3, config['exact_start']))
    exact_end_date = get_date((2024, 3, config['exact_end']))
    mocker.patch(
      'stock.models.Snapshot.end_date',
      new_callable=mocker.PropertyMock,
      return_value=exact_end_date,
    )
    # Define arguments
    options = {
      'title': 'sample',
      'start_date': get_date((2024, 3, config['start'])) if config['start'] else None,
    }
    if config['end']:
      options['end_date'] = get_date((2024, 3, config['end']))
    # Create instance
    user = get_user
    for _day in range(config['num_pstock']):
      purchase_date = get_date((2024, 3, 10 + _day)) # oldest day: 2024/3/10
      _ = factories.PurchasedStockFactory(user=user, purchase_date=purchase_date)
    instance = factories.SnapshotFactory(user=user, **options)
    instance.update_record()
    # Compare
    assert instance.start_date == exact_start_date
    assert instance.end_date == exact_end_date

  @pytest.mark.parametrize([
    'json_data',
  ], [
    ({'cash': {}, 'purchased_stocks': []},),
    ({'cash': {}, 'purchased_stocks': ['key0', 'something']},),
    ({'cash': {'key1': 'something'}, 'purchased_stocks': []},),
    ({'cash': {'key1': 'anything'}, 'purchased_stocks': ['key2']},),
  ], ids=[
    'both-are-empty',
    'cash-is-empty',
    'purchased-stock-is-empty',
    'both-are-included',
  ])
  def test_get_jsonfield_function(self, mocker, json_data):
    instance = factories.SnapshotFactory()
    mocker.patch.object(instance, 'detail', json.dumps(json_data))
    output = instance.get_jsonfield()
    extracted_uuid = re.search('(?<=id=")(.*?)(?=")', output).group(1)
    extracted_code = re.search('<script[^>]*?>(.*)</script>', output).group(1)
    extracted_json = json.loads(extracted_code)
    cash_key = 'cash'
    pstock_key = 'purchased_stocks'

    assert extracted_uuid == str(instance.uuid)
    assert all([key in extracted_json.keys() for key in json_data.keys()])
    assert all([len(extracted_json[key]) == len(val) for key, val in json_data.items()])
    assert all([extracted_json[cash_key][key] == exact_val] for key, exact_val in json_data[cash_key].items())
    assert all([estimated == exact_val for estimated, exact_val in zip(extracted_json[pstock_key], json_data[pstock_key])])

  @pytest.mark.parametrize([
    'title',
    'replaced',
  ], [ # \\|/|:|?|.|"|<|>|\|
    ('backslash\\string', 'backslash-string'),
    ('slash/string', 'slash-string'),
    ('colon:string', 'colon-string'),
    ('question?mark', 'question-mark'),
    ('period.', 'period-'),
    ('double"quotation', 'double-quotation'),
    ('less<than', 'less-than'),
    ('greater>than', 'greater-than'),
    ('pipe|symbol', 'pipe-symbol'),
    ('mu|ti"sym\\bols/', 'mu-ti-sym-bols-'),
  ], ids=[
    'backslash',
    'slash',
    'colon',
    'question-mark',
    'period',
    'double-quotation',
    'less-than',
    'greater-than',
    'pipe-symbol',
    'multi-symbols',
  ])
  def test_check_replace_title(self, title, replaced):
    instance = factories.SnapshotFactory(title=title)
    result = instance._replace_title()

    assert result == replaced

  @pytest.fixture(params=[
    (None, 'none'),
    (None, 'only'),
    (1000, 'diff'),
    (1100, 'same'),
  ], ids=[
    'no-cash-no-stocks',
    'only-one-stock',
    'cash-and-two-stocks',
    'cash-and-two-stocks-with-same-code',
  ], scope='class')
  def get_config(self, request, django_db_blocker):
    cash, stock_types = request.param
    all_purchased_stocks = [
      # No.1
      {
        'stock': {
          'code': 'A1B3',
          'names': {'en': 'en-hoge', 'ge': 'ge-hoge'},
          'industry': {
            'names': {'en': 'en-XXX', 'ge': 'ge-XXX'},
            'is_defensive': True,
          },
          'price': 1200.00,
          'dividend': 2.00,
          'per':      9.31,
          'pbr':      1.21,
          'eps':      2.34,
          'bps':      2.34,
          'roe':      0.34,
          'er':      11.22,
        },
        'price': 1234.00,
        'count': 100,
      },
      # No.2
      {
        'stock': {
          'code': 'A1CC',
          'names': {'en': 'en-bar', 'ge': 'ge-bar'},
          'industry': {
            'names': {'en': 'en-YYY', 'ge': 'ge-YYY'},
            'is_defensive': False,
          },
          'price':  900.00,
          'dividend': 1.00,
          'per':      7.50,
          'pbr':      2.22,
          'eps':      7.54,
          'bps':      8.12,
          'roe':      1.81,
          'er':      31.12,
        },
        'price': 1000.00,
        'count': 300,
      },
      # No.3
      {
        'stock': {
          'code': 'A1B3',
          'names': {'en': 'en-hoge', 'ge': 'ge-hoge'},
          'industry': {
            'names': {'en': 'en-XXX', 'ge': 'ge-XXX'},
            'is_defensive': True,
          },
          'price': 1200.00,
          'dividend': 2.00,
          'per':      9.31,
          'pbr':      1.21,
          'eps':      2.34,
          'bps':      2.34,
          'roe':      0.34,
          'er':      11.22,
        },
        'price': 1300.0,
        'count': 200,
      },
    ]
    # Create purchased stocks
    if stock_types == 'none':
      pstocks = []
    elif stock_types == 'only':
      pstocks = [all_purchased_stocks[0]]
    elif stock_types == 'diff':
      pstocks = [all_purchased_stocks[0], all_purchased_stocks[1]]
    else:
      pstocks = all_purchased_stocks
    # Define detail data
    data = json.dumps({
      'cash': {'balance': cash} if cash is not None else {},
      'purchased_stocks': pstocks,
    })
    # Define expected rows
    _cash_data = [
      '-', 'Cash', '-', '-', '0.00', '0.00', f'{cash:.2f}' if cash is not None else '0.00', # From code to pval
      '0', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00',                  # From count to er
    ]
    _only_data = [
      'A1B3', 'ge-hoge', 'ge-XXX', 'Defensive', '200.00', '0.16', '123400.00',       # From code to pval
      '100', '-3400.00', '1200.00', '9.31', '1.21', '2.34', '2.34', '0.34', '11.22', # From count to er
    ]
    _diff_data = [
      'A1CC', 'ge-bar', 'ge-YYY', 'Economically sensitive', '300.00', '0.10', '300000.00', # From code to pval
      '300', '-30000.00', '900.00', '7.50', '2.22', '7.54', '8.12', '1.81', '31.12',       # From count to er
    ]
    _same_data = [
      'A1B3', 'ge-hoge', 'ge-XXX', 'Defensive', '600.00', '0.16', '383400.00',        # From code to pval
      '300', '-23400.00', '1200.00', '9.31', '1.21', '2.34', '2.34', '0.34', '11.22', # From count to er
    ]
    if stock_types == 'none':
      expected_rows = [_cash_data]
      record_keys = ['cash']
      title = 'monthly report 20/12'
    elif stock_types == 'only':
      expected_rows = [_cash_data, _only_data]
      record_keys = ['cash', 'A1B3']
      title = 'monthly report 12/9'
    elif stock_types == 'diff':
      expected_rows = [_cash_data, _only_data, _diff_data]
      record_keys = ['cash', 'A1B3', 'A1CC']
      title = '月間レポート 21年12月'
    else:
      expected_rows = [_cash_data, _same_data, _diff_data]
      record_keys = ['cash', 'A1B3', 'A1CC']
      title = '月間レポート 19/08'

    with django_db_blocker.unblock():
      instance = factories.SnapshotFactory(user=factories.UserFactory(), title=title)
      instance.detail = data
      instance.save()

    return instance, expected_rows, record_keys

  def test_create_records(self, mocker, get_user, get_config):
    mocker.patch('stock.models.get_language', return_value='ge')
    instance, expected_rows, keys = get_config
    records = instance.create_records()
    formatter = lambda val: f'{val:.2f}'
    pairs = list(zip(keys, expected_rows))

    assert all([key in keys for key in records.keys()])
    assert all([          records[key].code             == arr[ 0] for key, arr in pairs])
    assert all([          records[key].name             == arr[ 1] for key, arr in pairs])
    assert all([          records[key].industry         == arr[ 2] for key, arr in pairs])
    assert all([          records[key].trend            == arr[ 3] for key, arr in pairs])
    assert all([formatter(records[key].real_div)        == arr[ 4] for key, arr in pairs])
    assert all([formatter(records[key].div_yield)       == arr[ 5] for key, arr in pairs])
    assert all([formatter(records[key].purchased_value) == arr[ 6] for key, arr in pairs])
    assert all([      str(records[key].count)           == arr[ 7] for key, arr in pairs])
    assert all([formatter(records[key].diff)            == arr[ 8] for key, arr in pairs])
    assert all([formatter(records[key].price)           == arr[ 9] for key, arr in pairs])
    assert all([formatter(records[key].per)             == arr[10] for key, arr in pairs])
    assert all([formatter(records[key].pbr)             == arr[11] for key, arr in pairs])
    assert all([formatter(records[key].eps)             == arr[12] for key, arr in pairs])
    assert all([formatter(records[key].bps)             == arr[13] for key, arr in pairs])
    assert all([formatter(records[key].roe)             == arr[14] for key, arr in pairs])
    assert all([formatter(records[key].er)              == arr[15] for key, arr in pairs])

  def test_create_response_kwargs(self, mocker, get_user, get_config):
    mocker.patch('stock.models.get_language', return_value='ge')
    instance, expected_rows, _ = get_config
    fname = instance._replace_title()
    expected_fname = 'snapshot-{}.csv'.format(urllib.parse.quote(fname.encode('utf-8')))
    header = [
      'Stock code', 'Name', 'Stock industry', 'Economic trend', 'Dividend', 'Dividend yield',
      'Purchased value', 'Number of stocks', 'Diff', 'Stock price', 'Price Earnings Ratio (PER)',
      'Price Book-value Ratio (PBR)', 'Earnings Per Share (EPS)', 'Book value Per Share (BPS)',
      'Return On Equity (ROE)', 'Equity Ratio (ER)',
    ]
    kwargs = instance.create_response_kwargs()
    rows = list(kwargs['rows'])

    assert all([est == exact for est, exact in zip(rows, expected_rows)])
    assert all([est == exact for est, exact in zip(kwargs['header'], header)])
    assert kwargs['filename'] == expected_fname

  @pytest.fixture(params=['none', 'only', 'both'], ids=[
    'no-cash-no-stocks',
    'only-one-stock',
    'cash-and-two-stocks',
  ])
  def get_json_stock_info(self, request):
    key = request.param

    if key == 'none':
      kwargs = {
        'title': 'none-data',
        'start_date': get_date((2021, 3, 24)),
        'end_date': get_date((2021, 4, 25)),
        'priority': 2,
      }
      detail = {
        'cash': {},
        'purchased_stocks': [],
      }
      this_tz = 'UTC'
    elif key == 'only':
      kwargs = {
        'title': 'only-data',
        'start_date': get_date((2021, 3, 25), tzinfo=ZoneInfo('Asia/Tokyo')),
        'end_date': get_date((2021, 4, 26), tzinfo=ZoneInfo('Asia/Tokyo')),
        'priority': 1,
      }
      detail = {
        'cash': {},
        'purchased_stocks': [{'price': 123.4, 'count': 200}],
      }
      this_tz = 'Asia/Tokyo'
    elif key == 'both':
      kwargs = {
        'title': '日本語タイトル',
        'start_date': get_date((2021, 3, 27)),
        'end_date': get_date((2021, 4, 28)),
        'priority': 99,
      }
      detail = {
        'cash': {'balance': 3456, 'registered_date': '2007-11-04T12:44:59'},
        'purchased_stocks': [{'price': 1547, 'purchase_date': '2022-01-03T02:34:54', 'count': 456}],
      }
      this_tz = 'UTC'

    return kwargs, detail, this_tz

  def test_create_json_from_model(self, settings, get_user, get_json_stock_info):
    kwargs, detail, this_tz = get_json_stock_info
    settings.TIME_ZONE = this_tz
    instance = factories.SnapshotFactory(
      user=get_user,
      **kwargs,
    )
    instance.detail = json.dumps(detail)
    instance.save()
    out = instance.create_json_from_model()
    fname = instance._replace_title()
    expected_filename = 'snapshot-{}.json'.format(urllib.parse.quote(fname.encode('utf-8')))
    expected_output = {
      'title': kwargs['title'],
      'detail': detail,
      'priority': kwargs['priority'],
      'start_date': kwargs['start_date'].isoformat(timespec='seconds'),
      'end_date': kwargs['end_date'].isoformat(timespec='seconds'),
    }

    assert out['filename'] == expected_filename
    assert out['data'] == expected_output

  def test_get_each_record(self, mocker, get_user, get_config):
    mocker.patch('stock.models.get_language', return_value='ge')
    instance, expected_rows, _ = get_config
    rows = [record for record in instance.get_each_record()]

    assert all([obj.get_record() == exact for obj, exact in zip(rows, expected_rows)])

  def test_update_periodic_task(self, get_user):
    user = get_user
    _ = factories.CashFactory.create_batch(2, user=user)
    _ = factories.PurchasedStockFactory.create_batch(3, user=user)
    snapshot = factories.SnapshotFactory(user=user)
    task = factories.PeriodicTaskFactory.build(crontab=None)
    crontab = factories.CrontabScheduleFactory()
    instance = snapshot.update_periodic_task(task, crontab)
    kwargs = json.loads(instance.kwargs)

    assert instance.crontab.pk == crontab.pk
    assert instance.task == 'stock.tasks.update_specific_snapshot'
    assert instance.description == snapshot.title
    assert kwargs['user_pk'] == user.pk
    assert kwargs['snapshot_pk'] == snapshot.pk

  @pytest.fixture(params=['unset', 'set'], ids=['unset-detail', 'set-detail'])
  def get_json_params(self, request):
    key = request.param
    expected = {
      'title': 'hogehoge-param',
      'start_date': get_date((2021, 3, 25)).isoformat(timespec='seconds'),
      'end_date': get_date((2021, 3, 25)).isoformat(timespec='seconds'),
      'priority': 3,
      'detail': '{"cash": {}, "purchased_stocks": []}',
    }
    kwargs = {
      'title': expected['title'],
      'start_date': expected['start_date'],
      'end_date': expected['end_date'],
      'priority': expected['priority'],
    }

    if key == 'set':
      expected['detail'] = '{"manual-data": "set"}'
      kwargs['detail'] = {
        'manual-data': 'set',
      }

    return kwargs, expected

  def test_check_create_instance_from_dict(self, settings, get_json_params, get_user):
    settings.TIME_ZONE = 'UTC'
    kwargs, expected = get_json_params
    user = get_user
    instance = models.Snapshot.create_instance_from_dict(user, kwargs)

    assert instance.title == expected['title']
    assert instance.start_date == expected['start_date']
    assert instance.end_date == expected['end_date']
    assert instance.priority == expected['priority']
    assert instance.detail == expected['detail']

  def test_check_get_instance_from_periodic_task_kwargs(self, get_user):
    user = get_user
    _ = factories.CashFactory.create_batch(2, user=user)
    _ = factories.PurchasedStockFactory.create_batch(3, user=user)
    snapshot = factories.SnapshotFactory(user=user)
    crontab = factories.CrontabScheduleFactory()
    task = factories.PeriodicTaskFactory(
      crontab=crontab,
      kwargs=json.dumps({'user_pk': user.pk, 'snapshot_pk': snapshot.pk}),
    )
    instance = models.Snapshot.get_instance_from_periodic_task_kwargs(task)

    assert instance.pk == snapshot.pk

  def test_exception_pattern_for_getting_instance_from_periodic_task_kwargs(self):
    task = factories.PeriodicTaskFactory(kwargs=json.dumps({'user_pk': 0, 'snapshot_pk': 0}))
    instance = models.Snapshot.get_instance_from_periodic_task_kwargs(task)

    assert instance is None

  @pytest.mark.parametrize([
    'pk_type',
    'exact_counts',
  ], [
    ('not-set', 2),
    ('set', 1),
  ], ids=[
    'snapshot-pk-is-not-set',
    'snapshot-pk-is-set',
  ])
  def test_check_get_queryset_from_periodic_task(self, get_user, pk_type, exact_counts):
    user = get_user
    other = factories.UserFactory()
    _ = factories.CashFactory.create_batch(2, user=user)
    _ = factories.PurchasedStockFactory.create_batch(3, user=user)
    ss1 = factories.SnapshotFactory(user=user)
    # Another snapshot
    _ = factories.CashFactory.create_batch(3, user=user)
    _ = factories.PurchasedStockFactory.create_batch(2, user=user)
    ss2 = factories.SnapshotFactory(user=user)
    # Other
    _ = factories.CashFactory.create_batch(2, user=other)
    _ = factories.PurchasedStockFactory.create_batch(2, user=other)
    _ = factories.SnapshotFactory(user=other)
    # Setup
    crontab = factories.CrontabScheduleFactory()
    task1 = factories.PeriodicTaskFactory(
      crontab=crontab,
      kwargs=json.dumps({'user_pk': user.pk, 'snapshot_pk': ss1.pk}),
    )
    task2 = factories.PeriodicTaskFactory(
      crontab=crontab,
      kwargs=json.dumps({'user_pk': user.pk, 'snapshot_pk': ss2.pk}),
    )
    if pk_type == 'not-set':
      config = {'user': user}
    else:
      config = {'user': user, 'pk': task2.pk}
    queryset = models.Snapshot.get_queryset_from_periodic_task(**config)

    assert queryset.count() == exact_counts

  def test_save_all_function(self, get_user):
    user = get_user
    stocks = factories.StockFactory.create_batch(3, price=123)
    c1 = factories.CashFactory(user=user, balance=1003, registered_date=get_date((2020, 3, 3)))
    c2 = factories.CashFactory(user=user, balance=1009, registered_date=get_date((2020, 3, 9)))
    c3 = factories.CashFactory(user=user, balance=1023, registered_date=get_date((2020, 3, 23)))
    _ = factories.PurchasedStockFactory(user=user, stock=stocks[0], price=234, purchase_date=get_date((2020, 3, 4)))
    _ = factories.PurchasedStockFactory(user=user, stock=stocks[1], price=100, purchase_date=get_date((2020, 3, 8)))
    _ = factories.PurchasedStockFactory(user=user, stock=stocks[2], price=300, purchase_date=get_date((2020, 3, 18)))
    # Create snapshots
    ss1 = factories.SnapshotFactory(user=user, start_date=get_date((2020, 3, 1)),  end_date=get_date((2020, 3, 15)))
    ss2 = factories.SnapshotFactory(user=user, start_date=get_date((2020, 3, 5)),  end_date=get_date((2020, 3, 20)))
    ss3 = factories.SnapshotFactory(user=user, start_date=get_date((2020, 3, 10)), end_date=get_date((2020, 3, 25)))
    #
    # Update cash and stocks
    #
    # Cash
    c1.balance = 2004
    c2.balance = 2010
    c3.balance = 2024
    for _c in [c1, c2, c3]:
      _c.save()
    # Stock
    stocks[0].price = 2345
    stocks[1].price = 3456
    stocks[2].price = 4567
    for _stock in stocks:
      _stock.save()
    # Call test method
    models.Snapshot.save_all(user)
    # Get new snapshots
    new_ss1 = models.Snapshot.objects.get(pk=ss1.pk)
    new_ss2 = models.Snapshot.objects.get(pk=ss2.pk)
    new_ss3 = models.Snapshot.objects.get(pk=ss3.pk)
    # Collect json data
    detail_ss1 = json.loads(new_ss1.detail)
    detail_ss2 = json.loads(new_ss2.detail)
    detail_ss3 = json.loads(new_ss3.detail)

    assert detail_ss1['cash']['balance'] == 2010
    assert detail_ss1['purchased_stocks'][0]['stock']['price'] == 3456
    assert detail_ss1['purchased_stocks'][1]['stock']['price'] == 2345
    assert detail_ss2['cash']['balance'] == 2010
    assert detail_ss2['purchased_stocks'][0]['stock']['price'] == 4567
    assert detail_ss2['purchased_stocks'][1]['stock']['price'] == 3456
    assert detail_ss3['cash']['balance'] == 2024
    assert detail_ss3['purchased_stocks'][0]['stock']['price'] == 4567

# ======================
# Delete related records
# ======================
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
class TestDeleteRecords:
  @pytest.mark.parametrize([
    'basename',
    'base_factory',
    'base_model',
    'target_factory',
    'target_model',
  ], [
    ('industry', factories.IndustryFactory, models.Industry, factories.StockFactory, models.Stock),
    ('user', factories.UserFactory, UserModel, factories.CashFactory, models.Cash),
    ('user', factories.UserFactory, UserModel, factories.PurchasedStockFactory, models.PurchasedStock),
    ('stock', factories.StockFactory, models.Stock, factories.PurchasedStockFactory, models.PurchasedStock),
  ], ids=[
    'industry-stock-pair',
    'user-cach-pair',
    'user-purchased-stock-pair',
    'stock-purchased-stock-pair',
  ])
  def test_delete_related_records(self, basename, base_factory, base_model, target_factory, target_model):
    expected_counts = 3
    instances = base_factory.create_batch(2)
    target_cases = [
      *target_factory.create_batch(5, **{basename: instances[0]}),
      *target_factory.create_batch(expected_counts, **{basename: instances[1]}),
    ]
    all_pks = [obj.pk for obj in target_cases]
    # Delete instance
    base_model.objects.get(pk=instances[0].pk).delete()
    rest_counts = target_model.objects.filter(pk__in=all_pks).count()

    assert rest_counts == expected_counts