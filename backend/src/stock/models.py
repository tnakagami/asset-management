from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, ValidationError
from django.utils.translation import gettext_lazy, get_language
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.html import json_script
from django_celery_beat.models import PeriodicTask
from types import FunctionType
from dataclasses import dataclass
from collections import deque
import urllib.parse
import re
import json
import uuid
import ast

UserModel = get_user_model()

def bind_user_function(callback):
  def wrapper(**kwargs):
    return callback(**kwargs)
  # Set function name
  wrapper.__name__ = 'as_udf' # user-defined function of asset-management

  return wrapper

def get_user_function(module):
  _is_function = lambda target: isinstance(target, FunctionType) and (target.__name__ == 'as_udf')
  attrs = [attr for attr in dir(module) if _is_function(getattr(module, attr))]
  name = getattr(module, 'stock_records_updater', None)

  if name in attrs:
    callback = getattr(module, name)
  else:
    callback = (lambda **kwargs: None)

  return callback

def convert_timezone(target, is_string=False, strformat=None):
  tz = timezone.get_current_timezone()
  output = target.astimezone(tz)

  if is_string:
    if strformat is None:
      output = output.isoformat(timespec='seconds')
    else:
      output = output.strftime(strformat)

  return output

def generate_default_filename():
  current_time = timezone.now()
  filename = convert_timezone(current_time, is_string=True, strformat='%Y%m%d-%H%M%S')

  return filename

class _AnalyzeAndCreateQmodelCondition(ast.NodeVisitor):
  def __init__(self, *args, **kwargs):
    self.q_cond = None
    self._data_stack = deque()
    self._comp_op_callbacks = {
      ast.Eq:    lambda name, val:  models.Q(**{f'{name}__exact': val}),
      ast.NotEq: lambda name, val: ~models.Q(**{f'{name}__exact': val}),
      ast.Lt:    lambda name, val:  models.Q(**{f'{name}__lt': val}),
      ast.LtE:   lambda name, val:  models.Q(**{f'{name}__lte': val}),
      ast.Gt:    lambda name, val:  models.Q(**{f'{name}__gt': val}),
      ast.GtE:   lambda name, val:  models.Q(**{f'{name}__gte': val}),
      ast.In:    lambda name, val:  models.Q(**{f'{name}__contains': val}),
      ast.NotIn: lambda name, val: ~models.Q(**{f'{name}__contains': val}),
    }
    self._swap_pairs = {
      ast.Lt:  ast.Gt(),
      ast.LtE: ast.GtE(),
      ast.Gt:  ast.Lt(),
      ast.GtE: ast.LtE(),
    }
    super().__init__(*args, **kwargs)

  @property
  def condition(self):
    return self.q_cond

  # Assumption: top module name is an expression
  def visit_Expression(self, node):
    self._data_stack.clear()
    self.visit(node.body)
    self.q_cond = self._data_stack.pop()

    return node

  def visit_BoolOp(self, node):
    _len = len(node.values)
    # Analysis each node
    for item in node.values:
      self.visit(item)
    # Create condition
    q_cond = models.Q()
    _op = models.Q.OR if isinstance(node.op, ast.Or) else models.Q.AND
    for _ in range(_len):
      item = self._data_stack.pop()
      q_cond.add(item, _op)
    self._data_stack.append(q_cond)

    return node

  def visit_Compare(self, node):
    _left = [node.left] + node.comparators[:-1]
    _right = list(node.comparators)
    count = 0

    for left_item, comp_op, right_item in zip(_left, node.ops, _right):
      if isinstance(left_item, ast.Constant) and isinstance(right_item, ast.Name):
        # Swap each item
        left_item, right_item = right_item, left_item

        for key, alter_op in self._swap_pairs.items():
          if isinstance(comp_op, key):
            comp_op = alter_op
            break

      # Analysis each node
      self.visit(left_item)
      self.visit(right_item)
      # Note: the right item position is upper than left item one because of using stack
      val = self._data_stack.pop()
      name = self._data_stack.pop()
      # Search matched operand
      for key, callback in self._comp_op_callbacks.items():
        if isinstance(comp_op, key):
          q_cond = callback(name, val)
          self._data_stack.append(q_cond)
          break
      count = count + 1

    q_cond = self._data_stack.pop()
    # Bind multi comparison
    for _ in range(count - 1):
      _q_item = self._data_stack.pop()
      q_cond &= _q_item
    # Store added items
    self._data_stack.append(q_cond)

    return node

  def visit_Name(self, node):
    self._data_stack.append(node.id)

    return node

  def visit_Constant(self, node):
    self._data_stack.append(node.value)

    return node

class LocalizedQuerySet(models.QuerySet):
  def select_current_lang(self):
    return self.filter(language_code=get_language())

  def get_local(self):
    default_lang = getattr(settings, 'LANGUAGE_CODE', 'en')

    for target in [get_language(), default_lang]:
      try:
        instance = self.get(language_code=target)
        break
      except self.model.DoesNotExist:
        pass
    else:
      instance = None

    return instance

class _BaseLocalization(models.Model):
  class Meta:
    abstract = True

  language_code = models.CharField(
    max_length=10,
    verbose_name=gettext_lazy('Language code'),
    choices=settings.LANGUAGES,
  )
  name = models.CharField(
    max_length=64,
    verbose_name=gettext_lazy('Localized name'),
    help_text=gettext_lazy('Max length of this field is 64.'),
  )

  def get_lang_pair(self):
    return (self.language_code, self.name)

  def __str__(self):
    return self.name

class LocalizedIndustry(_BaseLocalization):
  class Meta:
    unique_together = (('industry', 'language_code'), )

  objects = LocalizedQuerySet.as_manager()

  industry = models.ForeignKey(
    'Industry',
    verbose_name=gettext_lazy('Localized industry'),
    on_delete=models.CASCADE,
    related_name='locals',
  )

class IndustryManager(models.Manager):
  def get_queryset(self):
    return super().get_queryset().prefetch_related('locals')

class Industry(models.Model):
  is_defensive = models.BooleanField(
    verbose_name=gettext_lazy('Defensive brand'),
  )

  objects = IndustryManager()

  def get_dict(self):
    queryset = self.locals.all()

    return {
      'names': dict([record.get_lang_pair() for record in queryset]),
      'is_defensive': self.is_defensive,
    }

  def get_name(self):
    return str(self.locals.get_local() or '')

  def __str__(self):
    return self.get_name()

def _validate_code(code):
  invalid_match = re.search('[^0-9a-zA-Z]+', code)

  if invalid_match:
    raise ValidationError(
      gettext_lazy('You need to set either alphabets or numbers to this field.'),
      code='invalid',
      params={'value': code},
    )

class LocalizedStock(_BaseLocalization):
  class Meta:
    unique_together = (('stock', 'language_code'), )

  objects = LocalizedQuerySet.as_manager()

  stock = models.ForeignKey(
    'Stock',
    verbose_name=gettext_lazy('Localized stock'),
    on_delete=models.CASCADE,
    related_name='locals',
  )

class StockQuerySet(models.QuerySet):
  def _annotate_dividend(self):
    return self.annotate(
      div_yield=models.Case(
        models.When(price__gt=0, then=models.F('dividend')/models.F('price')*100.0),
        default=models.Value(0),
        output_field=models.FloatField(),
      )
    )

  def _annotate_per_pbr(self):
    return self.annotate(
      multi_pp=models.Case(
        models.When(per__gt=0, pbr__gt=0, then=models.F('per')*models.F('pbr')),
        default=models.Value(0),
        output_field=models.FloatField(),
      )
    )

  def _annotate_names(self):
    stocks = LocalizedStock.objects.select_current_lang().filter(stock=models.OuterRef('pk'))
    industries = LocalizedIndustry.objects.select_current_lang().filter(industry=models.OuterRef('industry__pk'))
    queryset = self.annotate(
      name=models.Subquery(stocks.values('name'))
    ).annotate(
      industry_name=models.Subquery(industries.values('name'))
    )

    return queryset

  def select_targets(self, tree=None):
    queryset = self.filter(skip_task=False) \
                   ._annotate_dividend() \
                   ._annotate_per_pbr() \
                   ._annotate_names()

    if tree:
      # Assumption: abstract syntax tree is validated by caller
      visitor = _AnalyzeAndCreateQmodelCondition()
      visitor.visit(tree)
      queryset = queryset.filter(visitor.condition)

    return queryset

class StockManager(models.Manager):
  def get_queryset(self):
    queryset = StockQuerySet(self.model, using=self._db)

    return queryset.select_related('industry').prefetch_related('locals')

  def select_targets(self, tree=None):
    return self.get_queryset().select_targets(tree)

class Stock(models.Model):
  class Meta:
    ordering = ('code',)
    constraints = [
      models.CheckConstraint(condition=models.Q(price__gte=0),    name='price_gte_0_in_stock'),
      models.CheckConstraint(condition=models.Q(dividend__gte=0), name='dividend_gte_0_in_stock'),
      models.CheckConstraint(condition=models.Q(per__gte=0),      name='per_gte_0_in_stock'),
      models.CheckConstraint(condition=models.Q(pbr__gte=0),      name='pbr_gte_0_in_stock'),
    ]

  objects = StockManager()

  code = models.CharField(
    max_length=16,
    verbose_name=gettext_lazy('Stock code'),
    help_text=gettext_lazy('This field consists of either only numbers or both alphabets and numbers.'),
    validators=[_validate_code],
    unique=True,
  )
  industry = models.ForeignKey(
    Industry,
    verbose_name=gettext_lazy('Stock industry'),
    on_delete=models.CASCADE,
    related_name='stocks',
  )
  price = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    verbose_name=gettext_lazy('Stock price'),
    default=0,
  )
  dividend = models.DecimalField(
    max_digits=7,
    decimal_places=2,
    verbose_name=gettext_lazy('Dividend'),
    default=0,
  )
  per = models.DecimalField(
    max_digits=7,
    decimal_places=2,
    verbose_name=gettext_lazy('PER'),
    help_text=gettext_lazy('Price Earnings Ratio'),
    default=0,
  )
  pbr = models.DecimalField(
    max_digits=7,
    decimal_places=2,
    verbose_name=gettext_lazy('PBR'),
    help_text=gettext_lazy('Price Book-value Ratio'),
    default=0,
  )
  eps = models.DecimalField(
    max_digits=7,
    decimal_places=2,
    verbose_name=gettext_lazy('EPS'),
    help_text=gettext_lazy('Earnings Per Share'),
    default=0,
  )
  bps = models.DecimalField(
    max_digits=7,
    decimal_places=2,
    verbose_name=gettext_lazy('BPS'),
    help_text=gettext_lazy('Book value Per Share'),
    default=0,
  )
  roe = models.DecimalField(
    max_digits=6,
    decimal_places=2,
    verbose_name=gettext_lazy('ROE'),
    help_text=gettext_lazy('Return On Equity'),
    default=0,
  )
  er = models.DecimalField(
    max_digits=5,
    decimal_places=2,
    verbose_name=gettext_lazy('ER'),
    help_text=gettext_lazy('Equity Ratio'),
    default=0,
  )
  skip_task = models.BooleanField(
    verbose_name=gettext_lazy('Skip executing user task'),
    default=False,
  )

  def save(self, *args, **kwargs):
    self.full_clean()
    super().save(*args, **kwargs)

  @classmethod
  def get_choices_as_list(cls):
    return list(cls.objects.select_targets().values('pk', 'name', 'code').order_by('pk'))

  def get_dict(self):
    queryset = self.locals.all()

    return {
      'code': self.code,
      'names': dict([record.get_lang_pair() for record in queryset]),
      'industry': self.industry.get_dict(),
      'price': float(self.price),
      'dividend': float(self.dividend),
      'per': float(self.per),
      'pbr': float(self.pbr),
      'eps': float(self.eps),
      'bps': float(self.bps),
      'roe': float(self.roe),
      'er': float(self.er),
    }

  def get_name(self):
    return str(self.locals.get_local() or '')

  @classmethod
  def get_response_kwargs(cls, filename, tree, ordering):
    if not filename:
      filename = generate_default_filename()
    name = urllib.parse.quote(filename.encode('utf-8'))
    queryset = cls.objects.select_targets(tree=tree).order_by(*ordering)
    rows = (
      [
        obj.code, obj.get_name(), str(obj.industry), str(obj.price), str(obj.dividend),
        f'{obj.div_yield:.2f}', str(obj.per), str(obj.pbr), f'{obj.multi_pp:.2f}',
        str(obj.eps), str(obj.bps), str(obj.roe), str(obj.er),
      ] for obj in queryset.iterator(chunk_size=512)
    )
    header = [
      gettext_lazy('Stock code'),
      gettext_lazy('Stock name'),
      gettext_lazy('Stock industry'),
      gettext_lazy('Stock price'),
      gettext_lazy('Dividend'),
      gettext_lazy('Dividend yield'),
      gettext_lazy('Price Earnings Ratio (PER)'),
      gettext_lazy('Price Book-value Ratio (PBR)'),
      gettext_lazy('PER x PBR'),
      gettext_lazy('Earnings Per Share (EPS)'),
      gettext_lazy('Book value Per Share (BPS)'),
      gettext_lazy('Return On Equity (ROE)'),
      gettext_lazy('Equity Ratio (ER)'),
    ]
    kwargs = {
      'rows': rows,
      'header': header,
      'filename': f'stock-{name}.csv',
    }

    return kwargs

  def __str__(self):
    return f'{self.get_name()}({self.code})'

class CashQuerySet(models.QuerySet):
  def selected_range(self, from_date=None, to_date=None):
    if from_date and to_date:
      queryset = self.filter(registered_date__range=[from_date, to_date])
    elif from_date:
      queryset = self.filter(registered_date__gte=from_date)
    elif to_date:
      queryset = self.filter(registered_date__lte=to_date)
    else:
      queryset = self

    return queryset

class Cash(models.Model):
  class Meta:
    ordering = ('-registered_date',)

  objects = CashQuerySet.as_manager()

  user = models.ForeignKey(
    UserModel,
    verbose_name=gettext_lazy('Owner'),
    on_delete=models.CASCADE,
    blank=True,
    related_name='cashes',
  )
  balance = models.PositiveIntegerField(
    verbose_name=gettext_lazy('Bank account balance'),
    help_text=gettext_lazy('This value is as of registered time.'),
  )
  registered_date = models.DateTimeField(
    verbose_name=gettext_lazy('Registered date'),
  )

  def get_dict(self):
    return {
      'balance': self.balance,
      'registered_date': convert_timezone(self.registered_date, is_string=True),
    }

  def __str__(self):
    target_time = convert_timezone(self.registered_date, is_string=True)
    out = f'{self.balance}({target_time})'

    return out

class PurchasedStockQuerySet(models.QuerySet):
  def older(self):
    return self.order_by('purchase_date')

  def _annotate_names(self):
    stocks = LocalizedStock.objects \
                           .select_current_lang() \
                           .filter(stock=models.OuterRef('stock'))
    industries = LocalizedIndustry.objects \
                                  .select_current_lang() \
                                  .filter(industry=models.OuterRef('stock__industry'))
    # Annotation
    queryset = self.annotate(
      code=models.F('stock__code')
    ).annotate(
      name=models.Subquery(stocks.values('name'))
    ).annotate(
      industry_name=models.Subquery(industries.values('name'))
    )

    return queryset

  def _annotate_diff(self):
    return self.annotate(
      diff=(models.F('stock__price')-models.F('price'))*models.F('count'),
    )

  def select_targets(self, tree=None):
    queryset = self.select_related('stock') \
                   .prefetch_related('stock__locals') \
                   ._annotate_names() \
                   ._annotate_diff()

    if tree:
      # Assumption: abstract syntax tree is validated by caller
      visitor = _AnalyzeAndCreateQmodelCondition()
      visitor.visit(tree)
      queryset = queryset.filter(visitor.condition)

    return queryset

  def selected_range(self, from_date=None, to_date=None):
    queryset = self.select_related('stock').filter(has_been_sold=False)

    if from_date and to_date:
      queryset = queryset.filter(purchase_date__range=[from_date, to_date])
    elif from_date:
      queryset = queryset.filter(purchase_date__gte=from_date)
    elif to_date:
      queryset = queryset.filter(purchase_date__lte=to_date)

    return queryset

class PurchasedStock(models.Model):
  class Meta:
    ordering = ('-purchase_date', 'stock__code')
    constraints = [
      models.CheckConstraint(condition=models.Q(price__gte=0), name='price_gte_0_in_purchased_stock'),
    ]

  objects = PurchasedStockQuerySet.as_manager()

  user = models.ForeignKey(
    UserModel,
    verbose_name=gettext_lazy('Owner'),
    on_delete=models.CASCADE,
    blank=True,
    related_name='purchased_stocks',
  )
  stock = models.ForeignKey(
    Stock,
    verbose_name=gettext_lazy('Target stock'),
    on_delete=models.CASCADE,
  )
  price = models.DecimalField(
    max_digits=11,
    decimal_places=2,
    verbose_name=gettext_lazy('Average trade price'),
    validators=[MinValueValidator(0)],
  )
  purchase_date = models.DateTimeField(
    verbose_name=gettext_lazy('Purchased date'),
  )
  count = models.IntegerField(
    verbose_name=gettext_lazy('The number of purchased stocks'),
    validators=[MinValueValidator(0)],
  )
  has_been_sold = models.BooleanField(
    verbose_name=gettext_lazy('Its stock has been sold or not'),
    default=False,
  )

  def get_dict(self):
    return {
      'stock': self.stock.get_dict(),
      'price': float(self.price),
      'purchase_date': convert_timezone(self.purchase_date, is_string=True),
      'count': self.count,
    }

  def save(self, *args, **kwargs):
    self.full_clean()
    super().save(*args, **kwargs)

  def __str__(self):
    target_time = convert_timezone(self.purchase_date, is_string=True)
    out = f'{self.stock.get_name()}({target_time},{self.count})'

    return out

@dataclass
class _SnapshotRecord:
  code: str
  price: float
  dividend: float
  per: float
  pbr: float
  eps: float
  bps: float
  roe: float
  er: float
  name: str = ''
  industry: str = ''
  trend: str = ''
  purchased_value: float = 0.0
  count: int = 0

  def _get_trend(self, is_defensive):
    table = {
      True: gettext_lazy('Defensive'),
      False: gettext_lazy('Economically sensitive'),
    }
    trend = table[is_defensive]

    return trend

  def _get_name(self, dict_item):
    if 'name' in dict_item.keys():
      name = dict_item['name']
    else:
      lang = get_language()
      name = dict_item['names'][lang]

    return name

  def set_name(self, stock):
    self.name = self._get_name(stock)

  def set_industry(self, industry):
    self.industry = self._get_name(industry)
    self.trend = self._get_trend(industry['is_defensive'])

  def add_count(self, count):
    self.count += count

  def add_value(self, value, count):
    self.purchased_value += value * float(count)

  @property
  def real_div(self):
    return self.dividend * self.count

  @property
  def div_yield(self):
    try:
      _yield = self.real_div / self.purchased_value * 100.0
    except:
      _yield = 0.0

    return _yield

  @property
  def stock_yield(self):
    try:
      _yield = self.dividend / self.price * 100.0
    except:
      _yield = 0.0

    return _yield

  @property
  def diff(self):
    if self.count > 0:
      total_price = self.price * self.count
      diff = total_price - self.purchased_value
    else:
      diff = 0.0

    return diff

  def get_record(self):
    formatter = lambda val: f'{val:.2f}'
    record = [
      self.code,
      self.name,
      self.industry,
      self.trend,
      formatter(self.real_div),
      formatter(self.div_yield),
      formatter(self.purchased_value),
      str(self.count),
      formatter(self.diff),
      formatter(self.price),
      formatter(self.per),
      formatter(self.pbr),
      formatter(self.eps),
      formatter(self.bps),
      formatter(self.roe),
      formatter(self.er),
    ]

    return record

  @classmethod
  def get_header(cls):
    header = [
      gettext_lazy('Stock code'),
      gettext_lazy('Name'),
      gettext_lazy('Stock industry'),
      gettext_lazy('Economic trend'),
      gettext_lazy('Dividend'),
      gettext_lazy('Dividend yield'),
      gettext_lazy('Purchased value'),
      gettext_lazy('Number of stocks'),
      gettext_lazy('Diff'),
      gettext_lazy('Stock price'),
      gettext_lazy('Price Earnings Ratio (PER)'),
      gettext_lazy('Price Book-value Ratio (PBR)'),
      gettext_lazy('Earnings Per Share (EPS)'),
      gettext_lazy('Book value Per Share (BPS)'),
      gettext_lazy('Return On Equity (ROE)'),
      gettext_lazy('Equity Ratio (ER)'),
    ]

    return header

class Snapshot(models.Model):
  class Meta:
    ordering = ('priority', '-end_date', )

  uuid = models.UUIDField(
    primary_key=False,
    default=uuid.uuid4,
    editable=False,
  )
  user = models.ForeignKey(
    UserModel,
    verbose_name=gettext_lazy('Owner'),
    on_delete=models.CASCADE,
    blank=True,
    related_name='snapshots',
  )
  title = models.CharField(
    max_length=255,
    verbose_name=gettext_lazy('Title'),
    help_text=gettext_lazy('Max length of this field is 255.'),
  )
  detail = models.JSONField(
    verbose_name=gettext_lazy('Relevant assets'),
    help_text=gettext_lazy('Relevant asset list as of created time (json format).'),
    blank=True,
  )
  priority = models.IntegerField(
    verbose_name=gettext_lazy('Priority to show the snapshot'),
    validators=[MinValueValidator(0)],
    default=99,
  )
  start_date = models.DateTimeField(
    verbose_name=gettext_lazy('Start date'),
    blank=True,
  )
  end_date = models.DateTimeField(
    verbose_name=gettext_lazy('End date'),
    default=timezone.now,
  )
  created_at = models.DateTimeField(
    verbose_name=gettext_lazy('Creation time'),
    default=timezone.now,
  )

  def update_record(self):
    if not self.start_date:
      oldest_record = self.user.purchased_stocks.older().first()

      if oldest_record:
        start_date = oldest_record.purchase_date
      else:
        start_date = self.end_date
    else:
      start_date = self.start_date
    # Collect cash and purchased stocks
    _cash = self.user.cashes.selected_range(from_date=self.start_date, to_date=self.end_date).first()
    _purchased_stocks = self.user.purchased_stocks.selected_range(from_date=self.start_date, to_date=self.end_date)
    self.start_date = start_date
    detail_dict = {
      'cash': _cash.get_dict() if _cash is not None else {},
      'purchased_stocks': [instance.get_dict() for instance in _purchased_stocks],
    }
    self.detail = json.dumps(detail_dict)

  def save(self, *args, **kwargs):
    if self.pk is None:
      self.update_record()
    super().save(*args, **kwargs)

  def __str__(self):
    target_time = convert_timezone(self.created_at, is_string=True)
    out = f'{self.title}({target_time})'

    return out

  def get_jsonfield(self):
    data = json.loads(self.detail)
    out = json_script(data, self.uuid)

    return out

  def _replace_title(self):
    return re.sub(r'[\\|/|:|?|.|"|<|>|\|]', '-', self.title)

  def create_records(self):
    data = json.loads(self.detail)
    records = {}
    #
    # Setup cash
    #
    records['cash'] = _SnapshotRecord(
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
      purchased_value=data['cash'].get('balance', 0.0),
    )
    #
    # Setup stocks
    #
    for record in data['purchased_stocks']:
      stock = record['stock']
      code = stock['code']
      instance = records.get(code, None)

      if instance is None:
        instance = _SnapshotRecord(
          code=code,
          price=stock['price'],
          dividend=stock['dividend'],
          per=stock['per'],
          pbr=stock['pbr'],
          eps=stock['eps'],
          bps=stock['bps'],
          roe=stock['roe'],
          er=stock['er'],
        )
        instance.set_name(stock)
        instance.set_industry(stock['industry'])
      # Update relevant data
      instance.add_count(record['count'])
      instance.add_value(record['price'], record['count'])
      records[code] = instance

    return records

  def create_response_kwargs(self):
    filename = self._replace_title()
    name = urllib.parse.quote(filename.encode('utf-8'))
    # Create records
    records = self.create_records()
    # Create output
    rows = (instance.get_record() for instance in records.values())
    kwargs = {
      'rows': rows,
      'header': _SnapshotRecord.get_header(),
      'filename': f'snapshot-{name}.csv',
    }

    return kwargs

  def create_json_from_model(self):
    filename = self._replace_title()
    name = urllib.parse.quote(filename.encode('utf-8'))
    data = {
      'title': self.title,
      'detail': json.loads(self.detail),
      'priority': self.priority,
      'start_date': convert_timezone(self.start_date, is_string=True),
      'end_date': convert_timezone(self.end_date, is_string=True),
    }
    out = {
      'data': data,
      'filename': f'snapshot-{name}.json',
    }

    return out

  def get_each_record(self):
    records = self.create_records()
    cash = records.pop('cash')
    all_snapshots = (records[key] for key in sorted(records.keys(), key=lambda val: val.zfill(6)))

    yield cash
    for snapshot in all_snapshots:
      yield snapshot

  def update_periodic_task(self, periodic_task, crontab):
    periodic_task.crontab = crontab
    periodic_task.task = 'stock.tasks.update_specific_snapshot'
    periodic_task.kwargs = json.dumps({'user_pk': self.user.pk, 'snapshot_pk': self.pk})
    periodic_task.description = self.title

    return periodic_task

  @classmethod
  def create_instance_from_dict(cls, user, params):
    update_keyname = 'detail'
    # Create instance
    instance = cls(user=user, **params)
    instance.save()
    # Update detail field
    if update_keyname in params.keys():
      instance.detail = json.dumps(params[update_keyname])
      instance.save(update_fields=[update_keyname])

    return instance

  @classmethod
  def get_instance_from_periodic_task_kwargs(cls, periodic_task):
    kwargs = json.loads(periodic_task.kwargs)
    pk = kwargs['snapshot_pk']
    # Get target instance
    try:
      instance = cls.objects.get(pk=pk)
    except cls.DoesNotExist:
      instance = None

    return instance

  @classmethod
  def get_queryset_from_periodic_task(cls, user, pk=None):
    # Convert dict object to string data without curly brackets
    params = {'kwargs__contains': json.dumps({'user_pk': user.pk})[1:-1]}
    # Add primary key of snapshot if it exists
    if pk is not None:
      params.update({'pk': pk})
    # Get queryset
    queryset = PeriodicTask.objects.filter(**params) \
                                   .prefetch_related('interval', 'crontab', 'solar', 'clocked') \
                                   .order_by('-total_run_count')

    return queryset

  @classmethod
  def save_all(cls, user):
    queryset = user.snapshots.all()
    records = []

    for instance in queryset:
      instance.update_record()
      records += [instance]
    # Update relevant fields
    cls.objects.bulk_update(records, fields=['detail'])