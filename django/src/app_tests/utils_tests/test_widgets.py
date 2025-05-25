import pytest
from django import forms
from django.contrib.auth import get_user_model
from dataclasses import dataclass
from utils import widgets

UserModel = get_user_model()

@dataclass
class _SelectWithDataAttrInfo():
  data_attr_name: str
  data_attrs: dict

@pytest.mark.utils
@pytest.mark.widget
@pytest.mark.parametrize([
  'attrs',
  'exact',
], [
  (
    {'data-attr-name': 'type', 'data-attrs': {'foo': 'hoge'}},
    _SelectWithDataAttrInfo(data_attr_name='type', data_attrs={'foo': 'hoge'}),
  ),
  (None, _SelectWithDataAttrInfo(data_attr_name='', data_attrs={})),
], ids=[
  'attrs-exist',
  'attrs-are-none',
])
def test_check_attrs_of_select_with_data_attr(attrs, exact):
  instance = widgets.SelectWithDataAttr(attrs=attrs)

  assert instance.data_attr_name == exact.data_attr_name
  assert len(instance.data_attrs) == len(exact.data_attrs)
  assert all([key in exact.data_attrs.keys() for key in instance.data_attrs.keys()])
  assert all([val == exact.data_attrs.get(key) for key, val in instance.data_attrs.items()])

@pytest.mark.utils
@pytest.mark.widget
@pytest.mark.parametrize([
  'attrs',
  'value',
  'exact',
], [
  ({'data-attr-name': 'type', 'data-attrs': {'foo': 'hoge'}}, 'foo', 'hoge'),
  ({'data-attr-name': 'type', 'data-attrs': {'foo': 'hoge'}}, 'hoge', 'none'),
  (None, 'hoge', None),
], ids=[
  'can-get-attr-of-option',
  'cannot-get-attr-of-option',
  'doesnot-set-attr',
])
def test_check_create_option_method_of_select_with_data_attr(attrs, value, exact):
  instance = widgets.SelectWithDataAttr(attrs=attrs)
  option = instance.create_option('sample', value, 'dummy', False, 0)
  estimated = option['attrs'].get('data-type')

  assert any([estimated is exact, estimated == exact])

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

  assert not instance._has_error
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

  assert all([key in out_widget.keys() for key in ['has_error', 'initial', 'type', 'id', 'use_dataset']])
  assert not out_widget['has_error']
  assert out_widget['initial'] == 3
  assert out_widget['type'] == 'text'
  assert out_widget['id'] == exact_id
  assert not out_widget['use_dataset']

@pytest.mark.utils
@pytest.mark.widget
@pytest.mark.parametrize([
  'value',
], [
  (0, ),
  ('a', ),
  (True, ),
  (False, ),
  ({}, ),
  ([], ),
  (None, ),
], ids=[
  'is-number',
  'is-string',
  'is-True',
  'is-False',
  'is-empty-dict',
  'is-empty-list',
  'is-None',
])
def test_check_has_error_setter(value):
  instance = widgets.Datalist(attrs=None)
  instance.has_error = value

  assert instance._has_error

@pytest.mark.utils
@pytest.mark.widget
def test_check_has_error_getter():
  instance = widgets.Datalist(attrs=None)

  with pytest.raises(AttributeError) as ex:
    _ = instance.has_error

  assert 'Invalid data access' in str(ex.value)

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