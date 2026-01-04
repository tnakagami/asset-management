from django import forms
from django.utils.translation import gettext_lazy
from django.utils.html import format_html
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from utils.forms import ModelFormBasedOnUser, BaseModelDatalistForm
from utils.widgets import (
  SelectWithDataAttr,
  DropdownWithInput,
  Datalist,
  ModelDatalistField,
  DropdownField,
  CustomRadioSelect,
)
from . import models
from collections import deque
import ast
import urllib.parse

def bool_converter(value):
  return value not in ['False', 'false', 'FALSE', '0', False]

class _BaseModelFormWithCSS(ModelFormBasedOnUser):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    for field in self.fields.values():
      _classes = field.widget.attrs.get('class', '')
      field.widget.attrs['class'] = f'{_classes} form-control'
      field.widget.attrs['placeholder'] = field.help_text

class CashForm(_BaseModelFormWithCSS):
  class Meta:
    model = models.Cash
    fields = ('balance', 'registered_date')
    widgets = {
      'registered_date': forms.DateInput(attrs={
        'id': 'registered-date-id',
        'class': 'datetimepicker-input',
      }),
    }

class CustomModelDatalistField(ModelDatalistField):
  def to_python(self, value):
    if value in self.empty_values:
      return None
    self.validate_no_null_characters(value)

    try:
      key = self.to_field_name or 'pk'

      if isinstance(value, self.queryset.model):
        value = getattr(value, key)
      value = self.queryset.model.objects.get(**{key: value})
    except (
      ValueError,
      TypeError,
      self.queryset.model.DoesNotExist,
      forms.ValidationError,
    ):
      raise forms.ValidationError(
        self.error_messages['invalid_choice'],
        code='invalid_choice',
        params={'value': value},
      )

    return value

class PurchasedStockForm(BaseModelDatalistForm, _BaseModelFormWithCSS):
  class Meta:
    model = models.PurchasedStock
    fields = ('stock', 'price', 'purchase_date', 'count', 'has_been_sold')
    widgets = {
      'stock': Datalist(attrs={
        'id': 'stock-id',
        'use-dataset': True,
        'class': 'form-control',
      }),
      'purchase_date': forms.DateInput(attrs={
        'id': 'purchase-date-id',
        'class': 'datetimepicker-input',
      }),
    }
    # For BaseModelDatalistForm
    datalist_fields = ['stock']
    datalist_kwargs = {
      'stock': {
        'label': gettext_lazy('Stock'),
        'queryset': models.Stock.objects.none(),
      },
    }

  has_been_sold = forms.TypedChoiceField(
    label=gettext_lazy('Has been sold/Is holding'),
    coerce=bool_converter,
    initial=False,
    empty_value=False,
    choices=(
      (True, gettext_lazy('Has been sold')),
      (False, gettext_lazy('Is holding')),
    ),
    widget=CustomRadioSelect(attrs={
      'class': 'form-check form-check-inline',
      'input-class': 'form-check-input',
      'label-class': 'form-check-label',
    }),
    help_text=gettext_lazy('Describes whether this purchased stock has been sold or not.'),
  )

  def __init__(self, *args, **kwargs):
    super().__init__(*args, field_class=CustomModelDatalistField, **kwargs)

  def is_valid(self):
    _is_valid = super().is_valid()

    if self.fields['stock'].error_messages:
      self.fields['stock'].widget.has_error = True

    return _is_valid

  def update_queryset(self, pk=None):
    purchased_stock = self._meta.model.objects.get(pk=pk)
    queryset = models.Stock.objects.filter(pk=purchased_stock.stock.pk)
    self.fields['stock'].queryset = queryset

class SnapshotForm(_BaseModelFormWithCSS):
  class Meta:
    model = models.Snapshot
    fields = ('title', 'start_date', 'end_date', 'priority', 'forced_update')
    widgets = {
      'start_date': forms.DateInput(attrs={
        'id': 'from-date-id',
        'class': 'datetimepicker-input',
      }),
      'end_date': forms.DateInput(attrs={
        'id': 'to-date-id',
        'class': 'datetimepicker-input',
      }),
    }

  forced_update = forms.TypedChoiceField(
    label=gettext_lazy('Force update/Nothing'),
    required=False,
    coerce=bool_converter,
    initial=False,
    empty_value=False,
    choices=(
      (True, gettext_lazy('Force update')),
      (False, gettext_lazy('Nothing')),
    ),
    help_text=gettext_lazy('Describes whether this record is forced update or not.'),
  )

  def save(self, commit=True):
    forced_update = self.cleaned_data.get('forced_update')
    instance = super().save(commit=False)

    if forced_update:
      instance.update_record()
    if commit:
      instance.save()

    return instance

class PeriodicTaskForSnapshotForm(forms.ModelForm):
  template_name = 'renderer/custom_form.html'

  class Meta:
    model = PeriodicTask
    fields = ('name', 'task', 'crontab', 'enabled', 'snapshot', 'schedule_type', 'config')
    field_order = ('name', 'snapshot', 'schedule_type', 'enabled', 'task', 'crontab', 'config')
    widgets = {
      'name': forms.TextInput(attrs={
        'class': 'form-control',
      }),
    }

  task = forms.CharField(
    label=gettext_lazy('Task name'),
    required=False,
    initial='---',
    widget=forms.HiddenInput(),
    max_length=4,
  )
  crontab = forms.ModelChoiceField(
    label=gettext_lazy('Crontab'),
    required=False,
    queryset=CrontabSchedule.objects.none(),
    empty_label=None,
    widget=forms.HiddenInput(),
  )
  enabled = forms.TypedChoiceField(
    label=gettext_lazy('Enabled/Disabled'),
    coerce=bool_converter,
    initial=True,
    empty_value=True,
    choices=(
      (True, gettext_lazy('Enabled')),
      (False, gettext_lazy('Disabled')),
    ),
    widget=forms.Select(attrs={
      'class': 'form-control',
    }),
    help_text=gettext_lazy('Describes whether this record is enabled or not.'),
  )
  snapshot = forms.ModelChoiceField(
    label=gettext_lazy('Snapshot'),
    queryset=models.Snapshot.objects.none(),
    empty_label=None,
    widget=forms.Select(attrs={
      'class': 'form-control',
    }),
    help_text=gettext_lazy('Select a snapshot to update.'),
  )
  schedule_type = forms.ChoiceField(
    label=gettext_lazy('Schedule type'),
    required=True,
    initial='every-day',
    choices=(
      ('every-day', gettext_lazy('Every day')),
      ('every-week', gettext_lazy('Every week')),
      ('every-month', gettext_lazy('Every month')),
    ),
    widget=forms.Select(attrs={
      'id': 'schedule-type',
      'class': 'form-control',
    }),
    help_text=gettext_lazy('Select a schedule type.'),
  )
  config = forms.JSONField(
    required=True,
    widget=forms.HiddenInput(attrs={
      'id': 'config',
      'name': 'config',
    }),
  )

  def __init__(self, user, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['snapshot'].queryset = user.snapshots.all()

  def clean(self):
    schedule_restriction = {
      'every-day': ['minute', 'hour'],
      'every-week': ['minute', 'hour', 'day_of_week'],
      'every-month': ['minute', 'hour', 'day_of_month'],
    }
    cleaned_data = super().clean()
    schedule_type = cleaned_data.get('schedule_type')
    config = cleaned_data.get('config')
    restriction = schedule_restriction[schedule_type]
    judgement = {key: key in restriction for key in config.keys()}

    # Validate config data
    if not all(list(judgement.values())):
      invalid_keys = ','.join([key for key, val in judgement.items() if not val])

      raise forms.ValidationError(
        gettext_lazy('Invalid keys: %(key)s'),
        code='invalid_data',
        params={'key': invalid_keys},
      )
    # Validate crontab instance
    kwargs = {key: config[key] for key in restriction}
    crontab = CrontabSchedule(**kwargs)
    crontab.full_clean()
    # Force update
    cleaned_data['crontab'] = crontab

    return cleaned_data

  def save(self, commit=True):
    snapshot = self.cleaned_data.get('snapshot')
    config = self.cleaned_data.get('config')
    crontab, _ = CrontabSchedule.objects.get_or_create(**config)
    periodic_task = super().save(commit=False)
    instance = snapshot.update_periodic_task(periodic_task, crontab)

    if commit:
      instance.save()

    return instance

class _IgnoredField:
  def clean(self, value, option):
    pass

class _ValidateCondition(ast.NodeVisitor):
  def __init__(self, *args, fields=None, comp_ops=None, **kwargs):
    # Define stock fields to check right operand
    _meta = models.Stock._meta
    _stock_fields = {
      'code': _meta.get_field('code'),
      'name': models.LocalizedStock._meta.get_field('name'),
      'industry_name': models.LocalizedIndustry._meta.get_field('name'),
      'price': _meta.get_field('price'),
      'dividend': _meta.get_field('dividend'),
      'div_yield': _IgnoredField(),
      'per': _meta.get_field('per'),
      'pbr': _meta.get_field('pbr'),
      'multi_pp': _IgnoredField(),
      'eps': _meta.get_field('eps'),
      'bps': _meta.get_field('bps'),
      'roe': _meta.get_field('roe'),
      'er': _meta.get_field('er'),
    }
    # Define comparison operators to check the relationship between variable and value
    _for_str = [ast.Eq, ast.NotEq, ast.In, ast.NotIn]
    _for_number = [ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE]
    _stock_comp_ops = {
      'code': _for_str,
      'name': _for_str,
      'industry_name': _for_str,
      'price': _for_number,
      'dividend': _for_number,
      'div_yield': _for_number,
      'per': _for_number,
      'pbr': _for_number,
      'multi_pp': _for_number,
      'eps': _for_number,
      'bps': _for_number,
      'roe': _for_number,
      'er': _for_number,
    }
    self._variables = {}
    self._operators = {}
    self._fields = fields or _stock_fields
    self._comp_ops = comp_ops or _stock_comp_ops
    self._stack = deque()
    super().__init__(*args, **kwargs)

  def validate(self):
    for key in self._variables.keys():
      vals = self._variables[key]
      ops = self._operators[key]

      try:
        field = self._fields[key]
        comp_ops = self._comp_ops[key]
      except KeyError:
        raise KeyError(gettext_lazy('%(key)s does not exist') % {'key': key})

      for value, operator in zip(vals, ops):
        try:
          field.clean(f'{value}', None)
        except forms.ValidationError as ex:
          raise forms.ValidationError(
            gettext_lazy('Invalid data (%(key)s, %(value)s): %(ex)s'),
            code='invalid_data',
            params={'key': key, 'value': str(value), 'ex': str(ex)},
          )

        if not any([isinstance(operator, _op) for _op in comp_ops]):
          raise forms.ValidationError(
            gettext_lazy('Invalid operator between %(key)s and %(value)s'),
            code='invalid_operator',
            params={'key': key, 'value': str(value)},
          )

  def visit(self, node):
    enable_classes = [
      'Expression',
      'BoolOp', 'And', 'Or',
      'Compare', 'Eq', 'NotEq', 'Lt', 'LtE', 'Gt', 'GtE', 'In', 'NotIn',
      'Name',
      'Constant',
    ]
    classname = node.__class__.__name__

    if classname not in enable_classes:
      raise SyntaxError(gettext_lazy('cannot use %(name)s in this application') % {'name': classname})

    return super().visit(node)

  def visit_Expression(self, node):
    self._stack.clear()
    self._variables = {}
    self.visit(node.body)

    return node

  def visit_Compare(self, node):
    _left = [node.left] + node.comparators[:-1]
    _right = list(node.comparators)

    for left_item, comp_op, right_item in zip(_left, node.ops, _right):
      if isinstance(left_item, ast.Constant) and isinstance(right_item, ast.Name):
        # Swap each item
        left_item, right_item = right_item, left_item
      # Analysis each node
      self.visit(left_item)
      self.visit(right_item)
      # Get relevant data
      var_value = self._stack.pop()
      var_name = self._stack.pop()
      # Add name-value pair to variable list
      old_vals = self._variables.get(var_name, [])
      old_ops = self._operators.get(var_name, [])
      self._variables[var_name] = old_vals + [var_value]
      self._operators[var_name] = old_ops + [comp_op]

    return node

  def visit_Name(self, node):
    self._stack.append(node.id)

    return node

  def visit_Constant(self, node):
    self._stack.append(node.value)

    return node

def validate_filtering_condition(value):
  condition = ' '.join(value.splitlines())
  visitor = _ValidateCondition()

  try:
    tree = ast.parse(condition, mode='eval')
    visitor.visit(tree)
    visitor.validate()
  except (SyntaxError, IndexError) as ex:
    raise forms.ValidationError(
      gettext_lazy('Invalid syntax: %(ex)s'),
      code='invalid_syntax',
      params={'ex': str(ex)},
    )
  except KeyError as ex:
    raise forms.ValidationError(
      gettext_lazy('Invalid variable: %(ex)s'),
      code='invalid_variable',
      params={'ex': str(ex)},
    )

class StockSearchForm(forms.Form):
  target = forms.ChoiceField(
    label=gettext_lazy('Target column name'),
    choices=(
      ('code', gettext_lazy('Stock code')),
      ('name', gettext_lazy('Stock name')),
      ('industry_name', gettext_lazy('Stock industry')),
      ('price', gettext_lazy('Stock price')),
      ('dividend', gettext_lazy('Dividend')),
      ('div_yield', gettext_lazy('Dividend yield')),
      ('per', gettext_lazy('Price Earnings Ratio')),
      ('pbr', gettext_lazy('Price Book-value Ratio')),
      ('multi_pp', format_html('{} &times; {}', 'PER', 'PBR')),
      ('eps', gettext_lazy('Earnings Per Share')),
      ('bps', gettext_lazy('Book value Per Share')),
      ('roe', gettext_lazy('Return On Equity')),
      ('er', gettext_lazy('Equity Ratio')),
    ),
    required=False,
    widget=SelectWithDataAttr(attrs={
      'class': 'form-control',
      'id': 'target-column-name',
      'data-attr-name': 'type',
      'data-attrs': {
        'code': 'str',
        'name': 'str',
        'industry_name': 'str',
        'price': 'number',
        'dividend': 'number',
        'div_yield': 'number',
        'per': 'number',
        'pbr': 'number',
        'multi_pp': 'number',
        'eps': 'number',
        'bps': 'number',
        'roe': 'number',
        'er': 'number',
      },
    }),
  )
  compop = forms.ChoiceField(
    label=gettext_lazy('Comparison operator'),
    choices=(
      ('==', gettext_lazy('Equal to')),
      ('!=', gettext_lazy('Not equal to')),
      ('>', gettext_lazy('Geater than')),
      ('>=', gettext_lazy('Geater than or equal to')),
      ('<', gettext_lazy('Less than')),
      ('<=', gettext_lazy('Less than or equal to')),
      ('in', gettext_lazy('Include')),
      ('not in', gettext_lazy('Not include')),
    ),
    required=False,
    widget=SelectWithDataAttr(attrs={
      'class': 'form-control',
      'id': 'comp-operator',
      'data-attr-name': 'type',
      'data-attrs': {
        '==': 'both',
        '!=': 'both',
        '>': 'number',
        '>=': 'number',
        '<': 'number',
        '<=': 'number',
        'in': 'str',
        'not in': 'str',
      },
    }),
  )
  inputs = forms.CharField(
    label=gettext_lazy('Input data'),
    empty_value='',
    required=False,
    widget=forms.TextInput(attrs={
      'class': 'form-control',
      'id': 'input-data',
    }),
  )
  condition = forms.CharField(
    label=gettext_lazy('Condition'),
    max_length=1024,
    empty_value='',
    required=False,
    widget=forms.Textarea(attrs={
      'class': 'form-control h-100',
      'id': 'condition',
      'name': 'condition',
      'rows': '10',
      'cols': '40',
      'style': 'resize: none;',
    }),
    validators=[validate_filtering_condition],
  )
  ordering = DropdownField(
    label=gettext_lazy('Ordering'),
    choices=(
      ('code', gettext_lazy('Stock code (ASC)')),
      ('-code', gettext_lazy('Stock code (DESC)')),
      ('name', gettext_lazy('Stock name (ASC)')),
      ('-name', gettext_lazy('Stock name (DESC)')),
      ('industry_name', gettext_lazy('Stock industry (ASC)')),
      ('-industry_name', gettext_lazy('Stock industry (DESC)')),
      ('price', gettext_lazy('Stock price (ASC)')),
      ('-price', gettext_lazy('Stock price (DESC)')),
      ('dividend', gettext_lazy('Dividend (ASC)')),
      ('-dividend', gettext_lazy('Dividend (DESC)')),
      ('div_yield', gettext_lazy('Dividend yield (ASC)')),
      ('-div_yield', gettext_lazy('Dividend yield (DESC)')),
      ('per', gettext_lazy('Price Earnings Ratio (ASC)')),
      ('-per', gettext_lazy('Price Earnings Ratio (DESC)')),
      ('pbr', gettext_lazy('Price Book-value Ratio (ASC)')),
      ('-pbr', gettext_lazy('Price Book-value Ratio (DESC)')),
      ('multi_pp', format_html('PER &times; PBR{}', gettext_lazy(' (ASC)'))),
      ('-multi_pp',  format_html('PER &times; PBR{}', gettext_lazy(' (DESC)'))),
      ('eps', gettext_lazy('Earnings Per Share (ASC)')),
      ('-eps', gettext_lazy('Earnings Per Share (DESC)')),
      ('bps', gettext_lazy('Book value Per Share (ASC)')),
      ('-bps', gettext_lazy('Book value Per Share (DESC)')),
      ('roe', gettext_lazy('Return On Equity (ASC)')),
      ('-roe', gettext_lazy('Return On Equity (DESC)')),
      ('er', gettext_lazy('Equity Ratio (ASC)')),
      ('-er', gettext_lazy('Equity Ratio (DESC)')),
    ),
    initial=['code'],
    required=False,
    widget=DropdownWithInput(attrs={
      'class': 'form-control',
      'id': 'column-ordering',
      'name': 'ordering',
      'disabled': True,
      'readonly': True,
    }),
  )

  def __init__(self, *args, **kwargs):
    params = kwargs.pop('data', None)
    # Convert message
    if params is not None:
      for key, val in params.items():
        if key == 'ordering':
          target = val.split(',')
        else:
          utf8str = val.encode('utf-8', 'ignore')
          target = urllib.parse.unquote(utf8str)
        params[key] = target
    super().__init__(*args, data=params, **kwargs)

  def get_queryset_with_condition(self):
    if self.is_valid():
      data = self.cleaned_data.get('condition', '')
      condition = ' '.join(data.splitlines())
      # Convert python like script to abstract syntax tree
      tree = ast.parse(condition, mode='eval') if condition else None
    else:
      tree = None
    # Get ordering of queryset
    ordering = self.cleaned_data.get('ordering') or ['code']
    # Get queryset
    queryset = models.Stock.objects.select_targets(tree=tree).order_by(*ordering)

    return queryset