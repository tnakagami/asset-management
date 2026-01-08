import pytest
import json
import re
import ast
from django.db.models import Q as dbQ
from django.db.utils import IntegrityError, DataError
from django.core.validators import ValidationError
from django.utils import timezone as djangoTimeZone
from django.contrib.auth import get_user_model
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from stock import models
from . import factories

UserModel = get_user_model()

@pytest.fixture
def get_judgement_funcs():
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
  ('UTC',        datetime(2010,3,15,20,15,0, tzinfo=timezone.utc), '2010-03-15'),
  ('Asia/Tokyo', datetime(2010,3,15,20,15,0, tzinfo=timezone.utc), '2010-03-16'),
], ids=lambda xs: '+'.join([xs[0], xs[1].strftime('%Y%m%d-%H:%M:%S'), xs[2]]))
def pseudo_date(request):
  yield request.param

@pytest.fixture
def pseudo_stock_data(django_db_blocker):
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_localized_industry():
  localized_industry = factories.LocalizedIndustryFactory()

  assert isinstance(localized_industry, models.LocalizedIndustry)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_industry():
  industry = factories.IndustryFactory()

  assert isinstance(industry, models.Industry)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_snapshot():
  snapshot = factories.SnapshotFactory()

  assert isinstance(snapshot, models.Snapshot)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_localized_stocky():
  localized_stock = factories.LocalizedStockFactory()

  assert isinstance(localized_stock, models.LocalizedStock)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_stock():
  stock = factories.StockFactory()

  assert isinstance(stock, models.Stock)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_cash():
  cash = factories.CashFactory()

  assert isinstance(cash, models.Cash)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_purchased_stock():
  purchased_stock = factories.PurchasedStockFactory()

  assert isinstance(purchased_stock, models.PurchasedStock)

# ================
# Global functions
# ================
@pytest.mark.stock
@pytest.mark.model
def test_check_bind_function():
  @models.bind_user_function
  def target_function():
    return 0

  ret = target_function()

  assert target_function.__name__ == 'as_udf'
  assert ret == 0

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.parametrize([
  'this_timezone',
  'target',
  'is_string',
  'strformat',
  'expected',
], [
  ('UTC', datetime(2000,1,2,10,0,0, tzinfo=timezone.utc), False, '', datetime(2000,1,2,10,0,0, tzinfo=ZoneInfo('UTC'))),
  ('UTC', datetime(2000,1,2,10,0,0, tzinfo=timezone.utc), True, '%Y-%m-%d %H:%M', '2000-01-02 10:00'),
  ('Asia/Tokyo', datetime(2000,1,2,10,0,0, tzinfo=timezone.utc), False, '', datetime(2000,1,2,19,0,0, tzinfo=ZoneInfo('Asia/Tokyo'))),
  ('Asia/Tokyo', datetime(2000,1,2,10,0,0, tzinfo=timezone.utc), True, '%Y-%m-%d %H:%M', '2000-01-02 19:00'),
], ids=[
  'to-utc-datetime',
  'to-utc-string',
  'to-asia-tokyo-datetime',
  'to-asia-tokyo-string',
])
def test_check_convert_timezone(settings, this_timezone, target, is_string, strformat, expected):
  settings.TIME_ZONE = this_timezone
  output = models.convert_timezone(target, is_string=is_string, strformat=strformat)

  assert output == expected

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.parametrize([
  'code',
], [
  ('1234', ),
  ('ABCD', ),
  ('xyzw', ),
  ('ABxy', ),
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
def test_check_valid_code_of_validate_code(code):
  try:
    models._validate_code(code)
  except Exception as ex:
    pytest.fail(f'Unexpected Error({code}): {ex}')

@pytest.mark.stock
@pytest.mark.model
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
def test_check_invalid_code_of_validate_code(code):
  with pytest.raises(ValidationError) as ex:
    models._validate_code(code)
  assert 'either alphabets or numbers' in str(ex.value)

# ===============
# QmodelCondition
# ===============
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.parametrize([
  'expression',
  'expected',
], [
  ('code == "0010"',                         dbQ(code__exact="0010")),
  ('code != "0010"',                        ~dbQ(code__exact="0010")),
  ('code in "001"',                          dbQ(code__contains="001")),
  ('code not in "001"',                     ~dbQ(code__contains="001")),
  ('price <= 1000',                          dbQ(price__lte=1000)),
  ('price < 1000',                           dbQ(price__lt=1000)),
  ('price >= 1000',                          dbQ(price__gte=1000)),
  ('price > 1000',                           dbQ(price__gt=1000)),
  ('price > 2 and er < 5',                   dbQ() & dbQ(er__lt=5) & (dbQ(price__gt=2))),
  ('price > 2 or er < 5',                    "(OR: (AND: ), (AND: ('er__lt', 5)), ('price__gt', 2))"),
  ('price > 2.01',                           dbQ(price__gt=2.01)),
  ('2.01 < price',                           dbQ(price__gt=2.01)),
  ('2 < er < 3',                             dbQ(er__lt=3) & dbQ(er__gt=2)),
  ('2 < er < 3 < bps < 5',                   dbQ(bps__lt=5) & dbQ(bps__gt=3) & dbQ(er__lt=3) & dbQ(er__gt=2)),
  ('2<er<3',                                 dbQ(er__lt=3) & dbQ(er__gt=2)),
  ('(price<5 or name in "001") and 2<er<3',  "(AND: ('er__lt', 3), ('er__gt', 2), (OR: (AND: ), (AND: ('name__contains', '001')), ('price__lt', 5)))"),
], ids=[
  'check-eq-exprn',
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
def test_q_model_condition(expression, expected):
  tree = ast.parse(expression, mode='eval')
  visitor = models._AnalyzeAndCreateQmodelCondition()
  visitor.visit(tree)
  estimated = visitor.condition

  assert str(estimated) == str(expected)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.parametrize([
  'condition',
], [
  ('price < 100',),
  ('100 < price',),
], ids=[
  'no-swap-pattern',
  'swap-pattern',
])
def test_no_pairs_for_q_model(condition):
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
def test_add_same_name_in_industry(name, language_code):
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_check_locals_of_industry(language_codes, exact_counts):
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_get_dict_function_of_industry():
  instance = factories.IndustryFactory()
  en_lang = factories.LocalizedIndustryFactory(language_code='en', industry=instance)
  ja_lang = factories.LocalizedIndustryFactory(language_code='ja', industry=instance)
  out_dict = instance.get_dict()

  assert all([key in ['names', 'is_defensive'] for key in out_dict.keys()])
  assert out_dict['is_defensive'] == instance.is_defensive
  assert out_dict['names'] == {'en': en_lang.name, 'ja': ja_lang.name}

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_check_industry_str_function_using_get_name_func(mocker, language_code, name, exact_name):
  mocker.patch('stock.models.get_language', return_value='en')
  instance = factories.IndustryFactory()
  lang = factories.LocalizedIndustryFactory(
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
def test_add_same_name_in_stock(name, language_code):
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_check_locals_of_stock(language_codes, exact_counts):
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'code',
], [
  ('1234', ),
  ('abcd', ),
  ('ABCD', ),
  ('12ab', ),
  ('12AB', ),
], ids=[
  'only-numbers',
  'only-small-letters',
  'only-capital-letters',
  'both-numbers-and-small-letters',
  'both-numbers-and-capital-letters',
])
def test_add_same_code_in_stock(code):
  _ = factories.StockFactory(code=code)

  with pytest.raises(ValidationError) as ex:
    _ = factories.StockFactory(code=code)
  assert 'Stock code already exists' in str(ex.value)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_check_valid_inputs_of_stock(options):
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_check_invalid_inputs_of_stock(options, err_idx, digit):
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_queryset_of_stock():
  _ = factories.StockFactory.create_batch(3, skip_task=True)
  _ = factories.StockFactory.create_batch(4, skip_task=False)
  all_counts = models.Stock.objects.all().count()
  specific = models.Stock.objects.select_targets().count()

  assert all_counts == 7
  assert specific == 4

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_qs_of_stock_with_tree(pseudo_stock_data, expression, indices):
  stock = pseudo_stock_data
  tree = ast.parse(expression, mode='eval')
  qs = models.Stock.objects.select_targets(tree=tree).order_by('pk')
  expected = [stock[idx].pk for idx in indices]

  assert qs.count() == len(expected)
  assert all([record.pk == pk for record, pk in zip(qs, expected)])

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_get_dict_function_of_stock(get_judgement_funcs):
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_check_stock_str_function_using_get_name_func(mocker, language_code, name, exact_name):
  mocker.patch('stock.models.get_language', return_value='en')
  code = 1234
  instance = factories.StockFactory(code=code)
  lang = factories.LocalizedStockFactory(
    name=name,
    language_code=language_code,
    stock=instance,
  )
  out = str(instance)
  expected = f'{exact_name}({code})'

  assert out == expected

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_choices_as_list_method(mocker):
  mocker.patch('stock.models.get_language', return_value='en')
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
def test_check_valid_balance_value(balance):
  user = factories.UserFactory()

  try:
    _ = models.Cash.objects.create(
      user=user,
      balance=balance,
      registered_date=djangoTimeZone.now(),
    )
  except IntegrityError as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_check_invalid_balance_value(balance, exception_type, err_msg):
  user = factories.UserFactory()

  with pytest.raises(exception_type) as ex:
    _ = models.Cash.objects.create(
      user=user,
      balance=balance,
      registered_date=djangoTimeZone.now(),
    )
  assert err_msg in str(ex.value)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_get_dict_function_of_cash(get_judgement_funcs):
  collector, compare_keys, compare_values = get_judgement_funcs
  target_date = datetime(2022,3,4,10,9,1, tzinfo=timezone.utc)
  instance = factories.CashFactory(
    registered_date=target_date,
  )
  out_dict = instance.get_dict()
  fields = collector(models.Cash, exclude=['user', 'registered_date'])
  _registered_date = out_dict.pop('registered_date', None)

  assert _registered_date is not None
  assert compare_keys(list(out_dict.keys()), fields)
  assert compare_values(fields, out_dict, instance)
  assert _registered_date == models.convert_timezone(target_date, is_string=True)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_cash_str_function(settings, pseudo_date):
  this_timezone, target_date, exact_date = pseudo_date
  settings.TIME_ZONE = this_timezone
  instance = factories.CashFactory(
    user=factories.UserFactory(),
    balance=12345,
    registered_date=target_date,
  )
  out = str(instance)
  expected = f'{instance.balance}({exact_date})'

  assert out == expected

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'from_day',
  'to_day',
  'count',
  'first_day',
  'last_day',
], [
  (10, 15, 4, 14, 10),
  (None, 9, 5, 7, 1),
  (25, None, 3, 30, 25),
  (None, None, 17, 30, 1),
], ids=[
  'both-date-are-given',
  'from-date-is-empty',
  'to-date-is-empty',
  'both-date-are-empty',
])
def test_selected_range_queryset_of_cash(from_day, to_day, count, first_day, last_day):
  get_date = lambda day: datetime(2023,5,day,5,6,7, tzinfo=timezone.utc)
  user, other = factories.UserFactory.create_batch(2)
  from_date = get_date(from_day) if from_day else None
  to_date = get_date(to_day) if to_day else None
  first_date = get_date(first_day)
  last_date = get_date(last_day)
  # Create records
  for _day in [1, 3, 5, 6, 7, 10, 11, 13, 14, 16, 17, 19, 20, 22, 25, 29, 30]:
    _ = factories.CashFactory(user=user, registered_date=get_date(_day))
  for _day in [9, 10, 14, 15, 16, 25, 26]:
    _ = factories.CashFactory(user=other, registered_date=get_date(_day))
  # Collect relevant queryset (order: '-registered_date')
  queryset = user.cashes.selected_range(from_date, to_date)
  _first = queryset.first()
  _last = queryset.last()

  assert len(queryset) == count
  assert all([record.user == user for record in queryset])
  assert _first.registered_date == first_date
  assert _last.registered_date == last_date

# ==============
# PurchasedStock
# ==============
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_check_valid_inputs_of_purchased_stock(options):
  kwargs = {
    'price': Decimal('1.23'),
    'count': 100,
  }
  kwargs.update(options)

  try:
    _ = models.PurchasedStock.objects.create(
      user=factories.UserFactory(),
      stock=factories.StockFactory(),
      purchase_date=datetime(1999,1,2,3,4,5, tzinfo=timezone.utc),
      **kwargs,
    )
  except ValidationError as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_check_invalid_inputs_of_purchased_stock(options, exception_type, err_msg):
  kwargs = {
    'price': Decimal('1.23'),
    'count': 100,
  }
  kwargs.update(options)

  with pytest.raises(exception_type) as ex:
    _ = models.PurchasedStock.objects.create(
      user=factories.UserFactory(),
      stock=factories.StockFactory(),
      purchase_date=datetime(1999,1,2,3,4,5, tzinfo=timezone.utc),
      **kwargs,
    )
  assert err_msg in str(ex.value)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'sold_out',
], [
  (True, ),
  (False, ),
], ids=[
  'has-been-sold',
  'has-not-been-sold',
])
def test_check_get_dict_function_of_purchased_stock(get_judgement_funcs, sold_out):
  collector, compare_keys, compare_values = get_judgement_funcs
  target_date = datetime(2022,3,4,10,9,1, tzinfo=timezone.utc)
  instance = factories.PurchasedStockFactory(
    purchase_date=target_date,
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
  assert _purchase_date == models.convert_timezone(target_date, is_string=True)

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_purchased_stock_str_function(mocker, settings, pseudo_date):
  mocker.patch('stock.models.get_language', return_value='en')
  this_timezone, target_date, exact_date = pseudo_date
  settings.TIME_ZONE = this_timezone
  stock = factories.StockFactory()
  instance = factories.PurchasedStockFactory(
    user=factories.UserFactory(),
    stock=stock,
    purchase_date=target_date,
    count=100,
  )
  _ = factories.LocalizedStockFactory(language_code='en', stock=stock)
  _ = factories.LocalizedStockFactory(language_code='ja', stock=stock)
  out = str(instance)
  expected = f'{instance.stock.get_name()}({exact_date},{instance.count})'

  assert out == expected

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_older_queryset_of_purchased_stock():
  user, other = factories.UserFactory.create_batch(2)
  get_date = lambda _day: datetime(2024,3,_day,1,2,3, tzinfo=timezone.utc)

  # 24/3/20, 24/3/19, 24/3/18
  exact0318 = get_date(18)
  exact0319 = get_date(19)
  exact0320 = get_date(20)
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'from_day',
  'to_day',
  'count',
  'first_day',
  'last_day',
], [
  (10, 15, 4, 14, 10),
  (None, 9, 5, 7, 1),
  (25, None, 3, 30, 25),
  (None, None, 17, 30, 1),
], ids=[
  'both-date-are-given',
  'from-date-is-empty',
  'to-date-is-empty',
  'both-date-are-empty',
])
def test_selected_range_queryset_of_purchased_stock(from_day, to_day, count, first_day, last_day):
  get_date = lambda day: datetime(2023,5,day,5,6,7, tzinfo=timezone.utc)
  user, other = factories.UserFactory.create_batch(2)
  from_date = get_date(from_day) if from_day else None
  to_date = get_date(to_day) if to_day else None
  first_date = get_date(first_day)
  last_date = get_date(last_day)
  # Create records
  for _day in [1, 3, 5, 6, 7, 10, 11, 13, 14, 16, 17, 19, 20, 22, 25, 29, 30]:
    _ = factories.PurchasedStockFactory(user=user, purchase_date=get_date(_day))
  for _day in [9, 10, 14, 15, 16, 25, 26]:
    _ = factories.PurchasedStockFactory(user=other, purchase_date=get_date(_day))
  # Collect relevant queryset (order: '-purchase_date')
  queryset = user.purchased_stocks.selected_range(from_date, to_date)
  _first = queryset.first()
  _last = queryset.last()

  assert len(queryset) == count
  assert all([record.user == user for record in queryset])
  assert _first.purchase_date == first_date
  assert _last.purchase_date == last_date

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_ignore_sold_stocks_of_purchased_stock():
  user = factories.UserFactory()
  pstocks = [
    factories.PurchasedStockFactory(user=user, has_been_sold=True),
    factories.PurchasedStockFactory(user=user, has_been_sold=False),
    factories.PurchasedStockFactory(user=user, has_been_sold=True),
  ]
  queryset = user.purchased_stocks.selected_range()
  the1st_instance = queryset.first()

  assert queryset.count() == 1
  assert the1st_instance.pk == pstocks[1].pk

# ========
# Snapshot
# ========
@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_that_json_field_is_empty_in_snapshot():
  instance = models.Snapshot.objects.create(
    user=factories.UserFactory(),
    title='Detail field is empty',
  )
  out_dict = json.loads(instance.detail)

  assert all(key in out_dict.keys() for key in ['cash', 'purchased_stocks'])
  assert len(out_dict['cash']) == 0
  assert len(out_dict['purchased_stocks']) == 0

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_check_that_cashes_exist_in_snapshot(balances, months_days, exact_idx):
  user = factories.UserFactory()

  for balance, month_day in zip(balances, months_days):
    target_date = datetime(2024,*month_day,1,2,3, tzinfo=timezone.utc)
    _ = factories.CashFactory(
      user=user,
      balance=balance,
      registered_date=target_date
    )

  instance = models.Snapshot.objects.create(
    user=user,
    title="User's cashes exist",
  )
  out_dict = json.loads(instance.detail)
  # Create exact data
  expected_balance = balances[exact_idx]
  expected_date = models.convert_timezone(
    datetime(2024,*(months_days[exact_idx]),1,2,3, tzinfo=timezone.utc),
    is_string=True,
  )

  assert all(key in out_dict.keys() for key in ['cash', 'purchased_stocks'])
  assert len(out_dict['cash']) == 2
  assert len(out_dict['purchased_stocks']) == 0
  assert out_dict['cash']['balance'] == expected_balance
  assert out_dict['cash']['registered_date'] == expected_date

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'number_of_purchased_stocks',
], [
  (1, ),
  (3, ),
], ids=[
  'only-one-purchased_stock-exists',
  'multi-purchased_stocks-exist',
])
def test_check_that_purchased_stocks_exist_in_snapshot(number_of_purchased_stocks):
  user = factories.UserFactory()
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_general_pattern_in_snapshot():
  user = factories.UserFactory()
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_snapshot_str_function(settings, pseudo_date):
  this_timezone, target_date, exact_date = pseudo_date
  settings.TIME_ZONE = this_timezone
  instance = factories.SnapshotFactory(
    user=factories.UserFactory(),
    title='sample-title',
    detail='{"key1":3,"key2":"a","key3":4}',
    created_at=target_date,
  )
  out = str(instance)
  expected = f'{instance.title}({exact_date})'

  assert out == expected

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_check_save_method_in_instance_update():
  user = factories.UserFactory()
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'start_day',
  'end_day',
  'num_purchased_stock',
  'expected_start_day',
  'expected_end_day',
], [
  (10, 15, 0, 10, 15),   # same as definition date
  (None, None, 0, 25, 25), # same as timezone.now
  (None, 15, 0, 15, 15), # same as end_date
  (None, 15, 2, 10, 15), # same as oldest date of purchased stock record
  (12, None, 0, 12, 25), # same as definition date
], ids=[
  'both-dates-exist',
  'both-dates-donot-exist',
  'start-date-and-purchased-stock-are-none',
  'start-date-is-none',
  'end-date-is-none',
])
def test_range_patterns_in_snapshot(mocker, start_day, end_day, num_purchased_stock, expected_start_day, expected_end_day):
  get_date = lambda day: datetime(2024,3,day,1,2,3, tzinfo=timezone.utc)
  # Calculate expected value
  expected_start_date = get_date(expected_start_day)
  expected_end_date = get_date(expected_end_day)
  mocker.patch(
    'stock.models.Snapshot.end_date',
    new_callable=mocker.PropertyMock,
    return_value=expected_end_date,
  )
  # Define arguments
  options = {
    'title': 'sample',
    'start_date': get_date(start_day) if start_day else None,
  }
  if end_day:
    options['end_date'] = get_date(end_day)
  # Create instance
  user = factories.UserFactory()
  for _day in range(num_purchased_stock):
    purchase_date = get_date(10 + _day) # oldest day: 2024/3/10
    _ = factories.PurchasedStockFactory(user=user, purchase_date=purchase_date)
  instance = factories.SnapshotFactory(user=user, **options)
  instance.update_record()
  # Compare
  assert instance.start_date == expected_start_date
  assert instance.end_date == expected_end_date

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_get_jsonfield_function_of_snapshot(mocker, json_data):
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_update_periodic_task():
  user = factories.UserFactory()
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_get_instance_from_periodic_task_kwargs():
  user = factories.UserFactory()
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_exception_pattern_for_getting_instance_from_periodic_task_kwargs():
  task = factories.PeriodicTaskFactory(kwargs=json.dumps({'user_pk': 0, 'snapshot_pk': 0}))
  instance = models.Snapshot.get_instance_from_periodic_task_kwargs(task)

  assert instance is None

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
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
def test_get_queryset_from_periodic_task(pk_type, exact_counts):
  user = factories.UserFactory()
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

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
def test_save_all_function_of_snapshot():
  get_date = lambda day: datetime(2020,3,day,3,4,5, tzinfo=timezone.utc)
  user = factories.UserFactory()
  stocks = factories.StockFactory.create_batch(3, price=123)
  c1 = factories.CashFactory(user=user, balance=1003, registered_date=get_date(3))
  c2 = factories.CashFactory(user=user, balance=1009, registered_date=get_date(9))
  c3 = factories.CashFactory(user=user, balance=1023, registered_date=get_date(23))
  _ = factories.PurchasedStockFactory(user=user, stock=stocks[0], price=234, purchase_date=get_date(4))
  _ = factories.PurchasedStockFactory(user=user, stock=stocks[1], price=100, purchase_date=get_date(8))
  _ = factories.PurchasedStockFactory(user=user, stock=stocks[2], price=300, purchase_date=get_date(18))
  # Create snapshots
  ss1 = factories.SnapshotFactory(user=user, start_date=get_date(1),  end_date=get_date(15))
  ss2 = factories.SnapshotFactory(user=user, start_date=get_date(5),  end_date=get_date(20))
  ss3 = factories.SnapshotFactory(user=user, start_date=get_date(10), end_date=get_date(25))
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
def test_delete_related_records(basename, base_factory, base_model, target_factory, target_model):
  expected_counts = 3
  instances = base_factory.create_batch(2)
  _ = target_factory.create_batch(5, **{basename: instances[0]})
  _ = target_factory.create_batch(expected_counts, **{basename: instances[1]})
  # Delete instance
  base_model.objects.get(pk=instances[0].pk).delete()
  rest_counts = target_model.objects.all().count()

  assert rest_counts == expected_counts