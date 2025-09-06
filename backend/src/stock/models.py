from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, ValidationError
from django.utils.translation import gettext_lazy
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.html import json_script
from zoneinfo import ZoneInfo
from collections import deque
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

def convert_timezone(target, is_string=False, strformat='%Y-%m-%d'):
  timezone = ZoneInfo(settings.TIME_ZONE)
  output = target.astimezone(timezone)

  if is_string:
    output = output.strftime(strformat)

  return output

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

class Industry(models.Model):
  name = models.CharField(
    max_length=64,
    verbose_name=gettext_lazy('Industry name'),
    help_text=gettext_lazy('Max length of this field is 64.'),
    unique=True,
  )
  is_defensive = models.BooleanField(
    verbose_name=gettext_lazy('Defensive brand'),
  )

  def get_dict(self):
    return {
      'name': self.name,
      'is_defensive': self.is_defensive,
    }

  def __str__(self):
    return self.name

def _validate_code(code):
  invalid_match = re.search('[^0-9a-zA-Z]+', code)

  if invalid_match:
    raise ValidationError(
      gettext_lazy('You need to set either alphabets or numbers to this field.'),
      code='invalid',
      params={'value': code},
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

  def select_targets(self, tree=None):
    queryset = self.filter(skip_task=False) \
                   ._annotate_dividend() \
                   ._annotate_per_pbr()

    if tree:
      # Assumption: abstract syntax tree is validated by caller
      visitor = _AnalyzeAndCreateQmodelCondition()
      visitor.visit(tree)
      queryset = queryset.filter(visitor.condition)

    return queryset

class Stock(models.Model):
  class Meta:
    ordering = ('code',)
    constraints = [
      models.CheckConstraint(condition=models.Q(price__gte=0),    name='price_gte_0_in_stock'),
      models.CheckConstraint(condition=models.Q(dividend__gte=0), name='dividend_gte_0_in_stock'),
      models.CheckConstraint(condition=models.Q(per__gte=0),      name='per_gte_0_in_stock'),
      models.CheckConstraint(condition=models.Q(pbr__gte=0),      name='pbr_gte_0_in_stock'),
    ]

  objects = StockQuerySet.as_manager()

  code = models.CharField(
    max_length=16,
    verbose_name=gettext_lazy('Stock code'),
    help_text=gettext_lazy('This field consists of either only numbers or both alphabets and numbers.'),
    validators=[_validate_code],
    unique=True,
  )
  name = models.CharField(
    max_length=255,
    verbose_name=gettext_lazy('Stock name'),
    help_text=gettext_lazy('Max length of this field is 255.'),
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
    return list(cls.objects.all().values('pk', 'name', 'code').order_by('pk'))

  def get_dict(self):
    return {
      'code': self.code,
      'name': self.name,
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

  def __str__(self):
    return f'{self.name}({self.code})'

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

  def selected_range(self, from_date=None, to_date=None):
    queryset = self.filter(has_been_sold=False)

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
    out = f'{self.stock.name}({target_time},{self.count})'

    return out

class Snapshot(models.Model):
  class Meta:
    ordering = ('-created_at', )

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

  @classmethod
  def save_all(cls, user):
    queryset = user.snapshots.all()
    records = []

    for instance in queryset:
      instance.update_record()
      records += [instance]
    # Update relevant fields
    cls.objects.bulk_update(records, fields=['detail'])