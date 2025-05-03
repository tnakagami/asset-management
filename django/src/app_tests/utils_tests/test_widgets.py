import pytest
from django import forms
from django.contrib.auth import get_user_model
from dataclasses import dataclass
from utils import widgets

UserModel = get_user_model()

@dataclass
class _DatalistInfo():
  input_type: str
  input_list: str
  use_dataset_attr: bool

@pytest.mark.utils
@pytest.mark.widget
@pytest.mark.parametrize([
  'attrs',
  'exact',
], [
  (
    {'type': 'select', 'list': 'dummy_list', 'use-dataset': True},
    _DatalistInfo(input_type='select', input_list='dummy_list', use_dataset_attr=True),
  ),
  (None, _DatalistInfo(input_type='text', input_list='', use_dataset_attr=False)),
], ids=[
  'attrs-exist',
  'attrs-are-none',
])
def test_check_attrs_of_datalist(attrs, exact):
  instance = widgets.Datalist(attrs=attrs)

  assert instance.input_type == exact.input_type
  assert instance.input_list == exact.input_list
  assert instance.use_dataset_attr == exact.use_dataset_attr

@pytest.mark.utils
@pytest.mark.widget
@pytest.mark.parametrize([
  'attrs',
  'exact_id',
], [
  (None, 'custom_datalist'),
  ({'list': 'dummy_list'}, 'dummy_list'),
], ids=['is-none', 'define-list'])
def test_check_context_of_datalist(attrs, exact_id):
  instance = widgets.Datalist(attrs=attrs)
  context = instance.get_context('custom', 3, attrs=None)
  out_widget = context['widget']

  assert all([key in out_widget.keys() for key in ['initial', 'type', 'id', 'use_dataset']])
  assert out_widget['initial'] == 3
  assert out_widget['type'] == 'text'
  assert out_widget['id'] == exact_id
  assert not out_widget['use_dataset']

@pytest.mark.utils
@pytest.mark.widget
def test_check_variables_of_datalist():
  instance = widgets.Datalist()
  exact_template_name = 'widgets/custom_datalist.html'
  exact_option_template_name = 'widgets/custom_datalist_option.html'

  assert instance.template_name == exact_template_name
  assert instance.option_template_name == exact_option_template_name
  assert not instance.use_dataset()

@pytest.mark.utils
@pytest.mark.widget
def test_check_init_func_of_datalist_field():
  instance = widgets.DatalistField(choices=())

  assert isinstance(instance.widget, widgets.Datalist)

@pytest.mark.utils
@pytest.mark.widget
@pytest.mark.django_db
@pytest.mark.parametrize([
  'widget',
  'exact_class',
], [
  (None, widgets.Datalist),
  (forms.Select, forms.Select),
], ids=['wiget-is-none', 'use-django-widget'])
def test_check_init_func_of_modeldatalist_field(widget, exact_class):
  instance = widgets.ModelDatalistField(queryset=UserModel.objects.none(), widget=widget)

  assert isinstance(instance.widget, exact_class)