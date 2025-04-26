from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy
from utils.forms import ModelFormBasedOnUser, ModelDatalistFormMixin
from utils.widgets import Datalist
from . import models

class PurchasedStockForm(ModelDatalistFormMixin, ModelFormBasedOnUser):
  class Meta:
    model = models.PurchasedStock
    fields = ('price', 'purchase_date', 'count')
    widgets = {
      'stock': Datalist(attrs={
        'id': 'stock-id',
        'use-dataset': True,
      }),
      'purchase_date': forms.DateInput(attrs={
        'id': 'purchase-date-id',
        'class': 'datetimepicker-input',
      }),
    }
    # For ModelDatalistFormMixin
    fields_ordering = ('stock', 'price', 'purchase_date', 'count')
    datalist_fields = ['stock']
    datalist_kwargs = {
      'stock': {
        'label': gettext_lazy('Stock'),
        'queryset': models.Stock.objects.all(),
      },
    }