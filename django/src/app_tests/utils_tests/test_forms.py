import pytest
from utils import forms, widgets
from stock import models

class DummyUser:
  pass

class DummyModelForm(forms.ModelFormBasedOnUser):
  class Meta:
    model = models.Industry
    fields = ('name',)

@pytest.mark.utils
@pytest.mark.form
def test_check_init_func_of_modelformbasedonuser():
  user = DummyUser()
  form = DummyModelForm(user=user)
  expect_template = 'renderer/custom_form.html'

  assert isinstance(form.user, DummyUser)
  assert form.template_name == expect_template

class DummyDatalistForm(forms.ModelDatalistFormMixin, forms.forms.ModelForm):
  class Meta:
    model = models.PurchasedStock
    fields = ('stock',)
    widgets = {
      'stock': widgets.Datalist(attrs={
        'id': 'stock-id',
        'use-dataset': True,
      }),
      'field2': widgets.Datalist(attrs={
        'id': 'field2-id',
        'use-dataset': True,
      }),
      'field3': widgets.Datalist(attrs={
        'id': 'field3-id',
      }),
    }
    datalist_fields = ['stock', 'field2', 'field3']
    datalist_kwargs = {
      'stock': {
        'label': 'Stock',
        'queryset': models.Stock.objects.all(),
      },
      'field2': {
        'label': 'field2',
        'queryset': models.Stock.objects.none(),
      },
      'field3': {
        'label': 'field3',
        'queryset': models.Stock.objects.none(),
      }
    }

@pytest.mark.utils
@pytest.mark.form
def test_check_member_variables_of_datalist_form():
  form = DummyDatalistForm()
  expect_template = 'renderer/custom_datalist_javascript.html'
  original_fields = ['stock', 'field2', 'field3']
  datalist_ids = form.datalist_ids

  assert form.datalist_template_name == expect_template
  assert all([val == original for val, original in zip(form._extra_datalist_fields, original_fields)])
  assert all([key in original_fields for key in form.declared_fields.keys()])
  assert 'stock-id' in datalist_ids
  assert 'field2-id' in datalist_ids