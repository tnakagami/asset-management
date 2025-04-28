from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy
from utils.forms import ModelFormBasedOnUser, ModelDatalistFormMixin
from utils.widgets import Datalist
from . import models

class _BaseModelFormWithCSS(ModelFormBasedOnUser):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    for field in self.fields.values():
      _classes = field.widget.attrs.get('class', '')
      field.widget.attrs['class'] = f'{_classes} form-control'
      field.widget.attrs['placeholder'] = field.help_text

class PurchasedStockForm(ModelDatalistFormMixin, _BaseModelFormWithCSS):
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
    # For ModelDatalistFormMixin
    datalist_fields = ['stock']
    datalist_kwargs = {
      'stock': {
        'label': gettext_lazy('Stock'),
        'queryset': models.Stock.objects.all(),
      },
    }

  @property
  def stock_choices(self):
    return self.fields['stock'].queryset.values('pk', 'name', 'code').order_by('pk')

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