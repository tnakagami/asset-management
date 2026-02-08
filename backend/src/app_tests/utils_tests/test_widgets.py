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
class TestSelectWithDataAttr:
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
  def test_check_attrs(self, attrs, exact):
    instance = widgets.SelectWithDataAttr(attrs=attrs)

    assert instance.data_attr_name == exact.data_attr_name
    assert len(instance.data_attrs) == len(exact.data_attrs)
    assert all([key in exact.data_attrs.keys() for key in instance.data_attrs.keys()])
    assert all([val == exact.data_attrs.get(key) for key, val in instance.data_attrs.items()])

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
  def test_check_create_option_method(self, attrs, value, exact):
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
class TestDatalist:
  def test_check_variables_of_datalist(self):
    instance = widgets.Datalist()

    assert instance.template_name == 'widgets/custom_datalist.html'
    assert instance.option_template_name == 'widgets/custom_datalist_option.html'
    assert not instance.use_dataset()

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
  def test_check_attrs(self, attrs, exact):
    instance = widgets.Datalist(attrs=attrs)

    assert not instance._has_error
    assert instance.input_type == exact.input_type
    assert instance.input_list == exact.input_list
    assert instance.use_dataset_attr == exact.use_dataset_attr

  @pytest.mark.parametrize([
    'attrs',
    'exact_id',
  ], [
    (None, 'custom_datalist'),
    ({'list': 'dummy_list'}, 'dummy_list'),
  ], ids=['is-none', 'define-list'])
  def test_check_context(self, attrs, exact_id):
    instance = widgets.Datalist(attrs=attrs)
    context = instance.get_context('custom', 3, attrs=None)
    out_widget = context['widget']

    assert all([key in out_widget.keys() for key in ['has_error', 'initial', 'type', 'id', 'use_dataset']])
    assert not out_widget['has_error']
    assert out_widget['initial'] == 3
    assert out_widget['type'] == 'text'
    assert out_widget['id'] == exact_id
    assert not out_widget['use_dataset']

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
  def test_check_has_error_setter(self, value):
    instance = widgets.Datalist(attrs=None)
    instance.has_error = value

    assert instance._has_error

  def test_check_has_error_getter(self):
    instance = widgets.Datalist(attrs=None)

    with pytest.raises(AttributeError) as ex:
      _ = instance.has_error

    assert 'Invalid data access' in str(ex.value)

@pytest.mark.utils
@pytest.mark.widget
class TestDropdownWithInput:
  def test_check_variables_of_dropdown_with_input(self):
    instance = widgets.DropdownWithInput()

    assert instance.input_type == 'text'
    assert instance.template_name == 'widgets/custom_dropdown.html'
    assert instance.option_template_name == 'widgets/custom_dropdown_option.html'

  def test_check_create_option_method(self):
    instance = widgets.DropdownWithInput()
    exact_value = 5
    option = instance.create_option('sample', exact_value, 'dummy', False, 0)
    estimated = option['attrs'].get('data-value', None)

    assert estimated == exact_value

  @pytest.mark.parametrize([
    'name',
    'value',
    'exact',
  ], [
    ('hoge', 'code', 'code'),
    ('foo', ['price', '-eps'], 'price,-eps'),
  ], ids=[
    'is-string',
    'is-list',
  ])
  def test_check_context_method(self, name, value, exact):
    instance = widgets.DropdownWithInput()
    context = instance.get_context(name, value, None)
    widget = context['widget']

    assert widget['type'] == 'text'
    assert widget['initial'] == exact
    assert widget['dropdown_id'] == f'{name}_dropdown'

@pytest.mark.utils
@pytest.mark.widget
class TestDatalistField:
  def test_check_init_func(self):
    instance = widgets.DatalistField(choices=())

    assert isinstance(instance.widget, widgets.Datalist)

@pytest.mark.utils
@pytest.mark.widget
@pytest.mark.django_db
class TestModelDatalistField:
  @pytest.mark.parametrize([
    'widget',
    'exact_class',
  ], [
    (None, widgets.Datalist),
    (forms.Select, forms.Select),
  ], ids=['wiget-is-none', 'use-django-widget'])
  def test_check_init_func_of_modeldatalist_field(self, widget, exact_class):
    instance = widgets.ModelDatalistField(queryset=UserModel.objects.none(), widget=widget)

    assert isinstance(instance.widget, exact_class)

@pytest.mark.utils
@pytest.mark.widget
class TestDropdownField:
  def test_check_init_func(self):
    instance = widgets.DropdownField(choices=())

    assert isinstance(instance.widget, widgets.DropdownWithInput)

  @pytest.mark.parametrize([
    'value',
    'exact',
  ], [
    (['foo'], ['foo']),
    ([], []),
    ([''], ['hoge']),
    (('',), ['hoge']),
  ], ids=[
    'call-super-method',
    'is-empty-list',
    'is-empty-string-list',
    'is-empty-string-tuple',
  ])
  def test_check_to_python_method(self, value, exact):
    instance = widgets.DropdownField(choices=(), initial=['hoge'])
    out = instance.to_python(value)

    assert len(out) == len(exact)
    assert all([val == original for val, original in zip(out, exact)])

@pytest.mark.utils
@pytest.mark.widget
class TestCustomRadioSelect:
  @pytest.mark.parametrize([
    'attrs',
    'expected_input',
    'expected_label',
  ], [
    ({'input-class': 'hoge', 'label-class': 'foo'}, 'hoge', 'foo'),
    (None, '', ''),
  ], ids=[
    'set-attributes',
    'not-set-attributes',
  ])
  def test_check_creat_option_method(self, attrs, expected_input, expected_label):
    widget = widgets.CustomRadioSelect(attrs)
    options = widget.create_option(
      name='bar',
      value=0,
      label='sub-label',
      selected=False,
      index=1,
    )
    keys = options.keys()

    assert 'input_class' in keys
    assert 'label_class' in keys
    assert options['input_class'] == expected_input
    assert options['label_class'] == expected_label