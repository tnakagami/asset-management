import pytest
from django.db.models.query import EmptyQuerySet
from django import forms as DjangoForms
from utils import forms, widgets
from stock import models

class DummyUser:
  pass

class DummyModelForm(forms.ModelFormBasedOnUser):
  class Meta:
    model = models.Cash
    fields = ('balance',)

@pytest.mark.utils
@pytest.mark.form
class TestModelFormBasedOnUser:
  def test_check_init_func(self):
    user = DummyUser()
    form = DummyModelForm(user=user)
    expect_template = 'renderer/custom_form.html'

    assert isinstance(form.user, DummyUser)
    assert form.template_name == expect_template

class DummyDatalistForm(forms.BaseModelDatalistForm, DjangoForms.ModelForm):
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
        'queryset': models.Stock.objects.none(),
      },
      'field3': {
        'label': 'other',
        'queryset': models.Stock.objects.none(),
      }
    }

class DatalistSampleForm(forms.BaseModelDatalistForm, DjangoForms.ModelForm):
  class Meta:
    model = models.PurchasedStock
    fields = ('stock',)
    widgets = {
      'stock': widgets.Datalist(attrs={
        'id': 'stock-id',
        'use-dataset': True,
      }),
    }
    datalist_fields = ['stock', 'field', 'other']
    datalist_kwargs = {
      'stock': {
        'label': 'Stock',
        'queryset': models.Stock.objects.all(),
      },
      'field': {
        'queryset': models.Stock.objects.none(),
      },
    }

@pytest.mark.utils
@pytest.mark.form
class TestDatalistForm:
  def test_check_member_variables(self):
    form = DummyDatalistForm()
    expect_template = 'renderer/custom_datalist_javascript.html'
    original_fields = ['stock', 'field2', 'field3']
    datalist_ids = form.datalist_ids

    assert form.datalist_template_name == expect_template
    assert form.fields['field3'].label == 'other'
    assert all([val == original for val, original in zip(form._extra_datalist_fields, original_fields)])
    assert all([key in original_fields for key in form.declared_fields.keys()])
    assert len(datalist_ids) == 2
    assert 'stock-id' in datalist_ids
    assert 'field2-id' in datalist_ids

  def test_check_lacking_variables(self):
    form = DatalistSampleForm()
    datalist_ids = form.datalist_ids

    assert not isinstance(form.fields['stock'].queryset, EmptyQuerySet)
    assert     isinstance(form.fields['field'].queryset, EmptyQuerySet)
    assert     isinstance(form.fields['other'].queryset, EmptyQuerySet)
    assert len(datalist_ids) == 1
    assert 'stock-id' in datalist_ids

class CustomModelDatalistField(widgets.ModelDatalistField):
  pass

class CustomFieldSampleForm(forms.BaseModelDatalistForm, DjangoForms.ModelForm):
  class Meta:
    model = models.PurchasedStock
    fields = ('stock',)
    widgets = {
      'stock': widgets.Datalist(attrs={
        'id': 'stock-id',
        'use-dataset': True,
      }),
    }
    datalist_fields = ['stock']
    datalist_kwargs = {
      'stock': {
        'label': 'Stock',
        'queryset': models.Stock.objects.none(),
      },
    }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, field_class=CustomModelDatalistField, **kwargs)

@pytest.mark.utils
@pytest.mark.form
class TestModelDatalistField:
  def test_check_using_modeldatalist(self):
    form = CustomFieldSampleForm()
    name = form.fields['stock'].__class__.__name__

    assert name == 'CustomModelDatalistField'