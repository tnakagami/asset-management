from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy
from utils.forms import ModelFormBasedOnUser, BaseModelDatalistForm
from utils.widgets import Datalist, ModelDatalistField
from . import models

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
    fields = ('stock', 'price', 'purchase_date', 'count')
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
    fields = ('title', 'start_date', 'end_date')
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