from django import forms
from django.core.validators import FileExtensionValidator
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.translation import gettext_lazy
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
from io import TextIOWrapper
import csv
import json
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

class UploadCsvPurchasedStockForm(forms.Form):
  template_name = 'renderer/custom_form.html'

  encoding = forms.ChoiceField(
    label=gettext_lazy('Encoding'),
    choices=(
      ('utf-8', 'UTF-8'),
      ('shift_jis', 'Shift-JIS'),
      ('cp932', 'CP932 (Windows)'),
    ),
    initial='utf-8',
    required=True,
    widget=forms.Select(attrs={
      'class': 'form-select',
      'autofocus': True,
    }),
    help_text=gettext_lazy('In general, please select "Shift-JIS" in Windows OS, "UTF-8" in Linux like OS.'),
  )

  csv_file = forms.FileField(
    label=gettext_lazy('CSV filename'),
    required=True,
    widget=forms.FileInput(attrs={
      'class': 'form-control',
      'style': 'padding: 2.5rem 1rem 1.75rem 1rem;',
    }),
    validators=[
      FileExtensionValidator(
        allowed_extensions=['csv'],
        message=gettext_lazy('The extention has to be ".csv".'),
      ),
    ],
    help_text=gettext_lazy('The extention is ".csv" only.'),
  )

  header = forms.TypedChoiceField(
    label=gettext_lazy('With header/Without header'),
    coerce=bool_converter,
    initial=True,
    empty_value=True,
    choices=(
      (True, gettext_lazy('With header')),
      (False, gettext_lazy('Without header')),
    ),
    widget=CustomRadioSelect(attrs={
      'class': 'form-check form-check-inline',
      'input-class': 'form-check-input',
      'label-class': 'form-check-label',
    }),
    help_text=gettext_lazy('Describes whether the csv file has header or not.'),
  )

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.valid_data = None
    self.length_checker = models.PurchasedStock.csv_length_checker
    self.extractor = models.PurchasedStock.csv_extractor
    self.record_checker = models.PurchasedStock.csv_record_checker

  def filtering(self, data):
    return [val for val in data if val != '']

  def validate_csv_file(self, csv_file, encoding, has_header):
    idx = 0

    try:
      with TextIOWrapper(csv_file, encoding=encoding) as text_file:
        # CSV format
        #   Code,Price,Purchase date,Count
        reader = csv.reader(text_file)
        records = []

        if has_header:
          next(reader)
        for idx, data in enumerate(reader, 1):
          row = self.filtering(data)
          is_valid = self.length_checker(row)

          if not is_valid:
            raise forms.ValidationError(
              gettext_lazy('The length in line %(idx)d is invalid.'),
              code='invalid_file',
              params={'idx': idx},
            )
          # Store the current row
          records += [self.extractor(row)]
        # Check specific columns
        self.record_checker(records)
        # Store valid data list to self.valid_data
        self.valid_data = records
    except UnicodeDecodeError as ex:
      raise forms.ValidationError(
        gettext_lazy('Failed to decode in line %(idx)d (Encoding: %(encoding)s).'),
        code='invalid_file',
        params={'idx': idx, 'encoding': str(ex.encoding)},
      )
    except (ValueError, TypeError, AttributeError) as ex:
      raise forms.ValidationError(
        gettext_lazy('Raise exception: %(ex)s.'),
        code='has_error',
        params={'ex': str(ex)},
      )

  def clean(self):
    cleaned_data = super().clean()
    csv_file = cleaned_data.get('csv_file')
    encoding = cleaned_data.get('encoding')
    has_header = cleaned_data.get('header')
    self.validate_csv_file(csv_file, encoding, has_header)

    return cleaned_data

  def get_data(self):
    return self.valid_data

  def register(self, user):
    instances = []

    try:
      enabled_items = [
        models.PurchasedStock.from_list(user, row)
        for row in self.get_data()
      ]
      with transaction.atomic():
        instances = models.PurchasedStock.objects.bulk_create(enabled_items)
    except IntegrityError as ex:
      error = forms.ValidationError(
        gettext_lazy('Include invalid records. Please check the detail: %(ex)s.'),
        code='invalid_records',
        params={'ex': str(ex)},
      )
      self.add_error(None, error)
    except Exception as ex:
      error = forms.ValidationError(
        gettext_lazy('Unexpected error occurred: %(ex)s.'),
        code='unexpected_err',
        params={'ex': str(ex)},
      )
      self.add_error(None, error)

    return instances

class DownloadCsvPurchasedStockForm(forms.Form):
  template_name = 'renderer/custom_form.html'

  filename = forms.CharField(
    label=gettext_lazy('CSV filename'),
    max_length=128,
    required=False,
    widget=forms.TextInput(attrs={
      'class': 'form-control',
      'id': 'download-filename',
      'autofocus': True,
    }),
    help_text=gettext_lazy('You don’t have to enter the extention.'),
  )

  def create_response_kwargs(self, user):
    filename = self.cleaned_data.get('filename', '').replace('.csv', '')
    # Create response kwargs
    kwargs = models.PurchasedStock.create_response_kwargs(filename, user)

    return kwargs

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

class UploadJsonFormatSnapshotForm(forms.Form):
  template_name = 'renderer/custom_form.html'

  encoding = forms.ChoiceField(
    label=gettext_lazy('Encoding'),
    choices=(
      ('utf-8', 'UTF-8'),
      ('shift_jis', 'Shift-JIS'),
      ('cp932', 'CP932 (Windows)'),
    ),
    initial='utf-8',
    required=True,
    widget=forms.Select(attrs={
      'class': 'form-select',
      'autofocus': True,
    }),
    help_text=gettext_lazy('In general, please select "Shift-JIS" in Windows OS, "UTF-8" in Linux like OS.'),
  )

  json_file = forms.FileField(
    label=gettext_lazy('JSON filename'),
    required=True,
    widget=forms.FileInput(attrs={
      'class': 'form-control',
      'style': 'padding: 2.5rem 1rem 1.75rem 1rem;',
    }),
    validators=[
      FileExtensionValidator(
        allowed_extensions=['json'],
        message=gettext_lazy('The extention has to be ".json".'),
      ),
    ],
    help_text=gettext_lazy('The extention is ".json" only.'),
  )

  def __init__(self, user, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.user = user
    self.valid_data = None

  def clean(self):
    cleaned_data = super().clean()
    json_file = cleaned_data.get('json_file')
    encoding = cleaned_data.get('encoding')

    try:
      with TextIOWrapper(json_file, encoding=encoding) as fin:
        self.valid_data = json.load(fin)
    except Exception as ex:
      raise forms.ValidationError(
        gettext_lazy('Cannot load json file: %(ex)s'),
        code='invalid_data',
        params={'ex': str(ex)},
      )

    return cleaned_data

  def register(self):
    instance = models.Snapshot.create_instance_from_dict(self.user, self.valid_data)

    return instance

class PeriodicTaskForSnapshotForm(forms.ModelForm):
  template_name = 'renderer/custom_form.html'

  class Meta:
    model = PeriodicTask
    fields = ('name', 'task', 'enabled', 'snapshot', 'schedule_type', 'config')
    field_order = ('name', 'snapshot', 'schedule_type', 'enabled', 'task', 'config')
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
    max_length=200,
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
    widget=forms.HiddenInput(attrs={
      'id': 'config',
      'name': 'config',
    }),
  )

  def __init__(self, user, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['snapshot'].queryset = user.snapshots.all()
    self.schedule_restriction = {
      'every-day': ['minute', 'hour'],
      'every-week': ['minute', 'hour', 'day_of_week'],
      'every-month': ['minute', 'hour', 'day_of_month'],
    }
    self.default_schedule = 'every-day'

  def update_initial(self, task):
    # Set pre-defined snapshot instance
    self.fields['snapshot'].initial = models.Snapshot.get_instance_from_periodic_task_kwargs(task)
    # Set base-config
    config = {
      'minute': task.crontab.minute,
      'hour': task.crontab.hour,
    }
    # Check crontab schedule
    if task.crontab.day_of_month != '*' and task.crontab.day_of_week == '*':
      self.fields['schedule_type'].initial = 'every-month'
      config['day_of_month'] = task.crontab.day_of_month
    elif task.crontab.day_of_month == '*' and task.crontab.day_of_week != '*':
      self.fields['schedule_type'].initial = 'every-week'
      config['day_of_week'] = task.crontab.day_of_week
    else:
      self.fields['schedule_type'].initial = 'every-day'
    # Update initial value of config data
    self.fields['config'].initial = json.dumps(config)

  def clean(self):
    cleaned_data = super().clean()
    schedule_type = cleaned_data.get('schedule_type', self.default_schedule)
    config = cleaned_data.get('config', {})
    restriction = self.schedule_restriction[schedule_type]
    given_keys = list(config.keys())
    rested = {key: key not in given_keys for key in restriction}

    # Validate config data
    if any(list(rested.values())):
      required_keys = ','.join([key for key, is_not_included in rested.items() if is_not_included])

      raise forms.ValidationError(
        gettext_lazy('Required keys: %(key)s'),
        code='invalid_data',
        params={'key': required_keys},
      )
    # Validate crontab instance
    kwargs = {key: config[key] for key in restriction}
    crontab = CrontabSchedule(**kwargs)
    # Execute full clean method
    try:
      crontab.full_clean()
    except forms.ValidationError as ex:
      raise forms.ValidationError(
        gettext_lazy('Invalid crontab config: %(err)s'),
          code='invalid_data',
          params={'err': str(ex)},
        )
    # Skip to execute `validate_unique` function when form.clean() is run.
    self._validate_unique = False

    return cleaned_data

  def save(self, commit=True):
    snapshot = self.cleaned_data.get('snapshot')
    config = self.cleaned_data.get('config')
    crontab, _ = CrontabSchedule.objects.get_or_create(**config)
    self.instance = snapshot.update_periodic_task(self.instance, crontab)
    instance = super().save(commit=False)

    if commit:
      instance.save()

    return instance

class StockSearchForm(forms.Form):
  target = forms.ChoiceField(
    label=gettext_lazy('Target column name'),
    choices=models.StockMembers.choices,
    required=False,
    widget=SelectWithDataAttr(attrs={
      'class': 'form-control',
      'id': 'target-column-name',
      'data-attr-name': 'type',
      'data-attrs': models.StockMembers.get_attribute_types(),
    }),
  )
  compop = forms.ChoiceField(
    label=gettext_lazy('Comparison operator'),
    choices=models.OperatorTypes.choices,
    required=False,
    widget=SelectWithDataAttr(attrs={
      'class': 'form-control',
      'id': 'comp-operator',
      'data-attr-name': 'type',
      'data-attrs': models.OperatorTypes.get_attribute_types(),
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
    validators=[models.stock_validator],
  )
  ordering = DropdownField(
    label=gettext_lazy('Ordering'),
    choices=models.StockOrderingTypes.choices,
    initial=[models.StockOrderingTypes.CODE_ASC],
    required=False,
    widget=DropdownWithInput(attrs={
      'class': 'form-control',
      'id': 'column-ordering',
      'name': 'ordering',
      'disabled': True,
      'readonly': True,
    }),
    validators=[models.stock_ordering_validator],
  )

  def __init__(self, *args, **kwargs):
    params = kwargs.pop('data', {})
    # Convert message
    for key, val in params.items():
      if key == 'ordering':
        target = models.StockOrderingTypes.separate(val)
      else:
        utf8str = val.encode('utf-8', 'ignore')
        target = urllib.parse.unquote(utf8str)
      params[key] = target
    super().__init__(*args, data=params, **kwargs)

  def get_queryset_with_condition(self):
    if self.is_valid():
      data = self.cleaned_data.get('condition', '')
      tree = models.get_tree(data)
    else:
      tree = None
    # Get ordering of queryset
    ordering = self.cleaned_data.get('ordering') or [models.StockOrderingTypes.CODE_ASC]
    # Get queryset
    queryset = models.Stock.objects.select_targets(tree=tree).order_by(*ordering)

    return queryset

class PurchasedStockFilteringForm(forms.Form):
  target = forms.ChoiceField(
    label=gettext_lazy('Target column name'),
    choices=models.PurchasedStockMembers.choices,
    required=False,
    widget=SelectWithDataAttr(attrs={
      'class': 'form-control',
      'id': 'target-column-name',
      'data-attr-name': 'type',
      'data-attrs': models.PurchasedStockMembers.get_attribute_types(),
    }),
  )
  compop = forms.ChoiceField(
    label=gettext_lazy('Comparison operator'),
    choices=models.OperatorTypes.choices,
    required=False,
    widget=SelectWithDataAttr(attrs={
      'class': 'form-control',
      'id': 'comp-operator',
      'data-attr-name': 'type',
      'data-attrs': models.OperatorTypes.get_attribute_types(),
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
    validators=[models.purchased_stock_validator],
  )

  def __init__(self, *args, **kwargs):
    params = kwargs.pop('data', {})
    # Convert message
    for key, val in params.items():
      target = val.encode('utf-8', 'ignore')
      params[key] = urllib.parse.unquote(target)
    super().__init__(*args, data=params, **kwargs)

  def get_queryset_with_condition(self, user):
    if self.is_valid():
      data = self.cleaned_data.get('condition', '')
      tree = models.get_tree(data)
    else:
      tree = None
    # Get queryset
    queryset = user.purchased_stocks.select_targets(tree=tree)

    return queryset

class StockDownloadForm(forms.Form):
  template_name = 'renderer/custom_form.html'

  filename = forms.CharField(
    label=gettext_lazy('CSV filename'),
    max_length=128,
    required=False,
    widget=forms.TextInput(attrs={
      'class': 'form-control',
      'id': 'download-filename',
      'autofocus': True,
    }),
    help_text=gettext_lazy('You don’t have to enter the extention.'),
  )
  condition = forms.CharField(
    label='',
    empty_value='',
    required=False,
    widget=forms.Textarea(attrs={
      'id': 'download-condition',
      'style': 'display: none;',
    }),
  )
  ordering = forms.CharField(
    label=gettext_lazy('Ordering'),
    max_length=1024,
    empty_value='',
    required=False,
    widget=forms.HiddenInput(attrs={
      'id': 'download-ordering',
    }),
  )
  allowed_long_condition = forms.BooleanField(
    label=gettext_lazy('Allowed long condition'),
    required=False,
    initial=False,
    widget=forms.HiddenInput(),
  )

  def __init__(self, *args, max_condition_length=1024, **kwargs):
    self.max_condition_length = max_condition_length
    super().__init__(*args, **kwargs)

  def clean(self):
    cleaned_data = super().clean()
    condition = cleaned_data.get('condition')
    allowed_long_condition = cleaned_data.get('allowed_long_condition')

    if not allowed_long_condition and len(condition) > self.max_condition_length:
      self.add_error('condition', gettext_lazy('Condition is too long. Please enter more short condition.'))

    return cleaned_data

  def get_query_string(self):
    condition = self.cleaned_data.get('condition', '')
    ordering = self.cleaned_data.get('ordering', '')
    query_string = urllib.parse.quote(f'condition={condition}&ordering={ordering}')

    return query_string

  def create_response_kwargs(self):
    filename = self.cleaned_data.get('filename', '').replace('.csv', '')
    ordering = self.cleaned_data.get('ordering', '')
    data = self.cleaned_data.get('condition', '')
    qs_order = [models.StockOrderingTypes.CODE_ASC.value]

    try:
      # Check condition
      models.stock_validator(data)
      tree = models.get_tree(data)
    except forms.ValidationError:
      tree = None
    # Check ordering
    if ordering:
      try:
        qs_order = models.StockOrderingTypes.separate(ordering)
        models.stock_ordering_validator(qs_order)
      except forms.ValidationError:
        qs_order = [models.StockOrderingTypes.CODE_ASC.value]
    # Create response kwargs
    kwargs = models.Stock.create_response_kwargs(filename, tree, qs_order)

    return kwargs

class StockScreenerForm(_BaseModelFormWithCSS):
  class Meta:
    model = models.StockScreener
    fields = ('title', 'priority', 'condition', 'ordering')
    field_order = ('title', 'priority', 'condition', 'ordering', 'target', 'compop', 'inputs')
    widgets = {
      'condition': forms.Textarea(attrs={
        'class': 'h-100',
        'id': 'condition',
        'name': 'condition',
        'rows': '10',
        'cols': '40',
        'style': 'resize: none;',
      }),
      'ordering': forms.TextInput(attrs={
        'id': 'column-ordering',
        'name': 'ordering',
        'disabled': True,
        'readonly': True,
      }),
    }

  @property
  def ordering_types(self):
    return models.StockOrderingTypes.choices

  target = forms.ChoiceField(
    label=gettext_lazy('Target column name'),
    choices=models.StockMembers.choices,
    required=False,
    widget=SelectWithDataAttr(attrs={
      'class': 'form-control',
      'id': 'target-column-name',
      'data-attr-name': 'type',
      'data-attrs': models.StockMembers.get_attribute_types(),
    }),
  )
  compop = forms.ChoiceField(
    label=gettext_lazy('Comparison operator'),
    choices=models.OperatorTypes.choices,
    required=False,
    widget=SelectWithDataAttr(attrs={
      'class': 'form-control',
      'id': 'comp-operator',
      'data-attr-name': 'type',
      'data-attrs': models.OperatorTypes.get_attribute_types(),
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