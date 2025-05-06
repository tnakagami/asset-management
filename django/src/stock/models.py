from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, ValidationError
from django.utils.translation import gettext_lazy
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.html import json_script
from zoneinfo import ZoneInfo
import re
import json
import uuid

UserModel = get_user_model()

def convert_timezone(target, is_string=False, strformat='%Y-%m-%d'):
  timezone = ZoneInfo(settings.TIME_ZONE)
  output = target.astimezone(timezone)

  if is_string:
    output = output.strftime(strformat)

  return output

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
    raise ValidationError(gettext_lazy('You need to set either alphabets or numbers to this field.'))

class Stock(models.Model):
  class Meta:
    ordering = ('code',)
    constraints = [
      models.CheckConstraint(condition=models.Q(price__gte=0),    name='price_gte_0_in_stock'),
      models.CheckConstraint(condition=models.Q(dividend__gte=0), name='dividend_gte_0_in_stock'),
      models.CheckConstraint(condition=models.Q(per__gte=0),      name='per_gte_0_in_stock'),
      models.CheckConstraint(condition=models.Q(pbr__gte=0),      name='pbr_gte_0_in_stock'),
      models.CheckConstraint(condition=models.Q(eps__gte=0),      name='eps_gte_0_in_stock'),
    ]

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
    if from_date and to_date:
      queryset = self.filter(purchase_date__range=[from_date, to_date])
    elif from_date:
      queryset = self.filter(purchase_date__gte=from_date)
    elif to_date:
      queryset = self.filter(purchase_date__lte=to_date)
    else:
      queryset = self

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

  def save(self, *args, **kwargs):
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

    super().save(*args, **kwargs)

  def __str__(self):
    target_time = convert_timezone(self.created_at, is_string=True)
    out = f'{self.title}({target_time})'

    return out

  def get_jsonfield(self):
    data = json.loads(self.detail)
    out = json_script(data, self.uuid)

    return out