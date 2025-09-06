from django import forms

class SelectWithDataAttr(forms.Select):
  data_attr_name = ''
  data_attrs = {}

  def __init__(self, *args, attrs=None, **kwargs):
    if attrs is not None:
      self.data_attr_name = attrs.pop('data-attr-name', self.data_attr_name)
      self.data_attrs = attrs.pop('data-attrs', self.data_attrs)
    super().__init__(*args, attrs=attrs, **kwargs)

  def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
    option = super().create_option(name, value, label, selected, index, subindex, attrs)

    if self.data_attr_name:
      option['attrs'][f'data-{self.data_attr_name}'] = self.data_attrs.get(value, 'none')

    return option

class Datalist(forms.Select):
  input_type = 'text'
  input_list = ''
  use_dataset_attr = False
  template_name = 'widgets/custom_datalist.html'
  option_template_name = 'widgets/custom_datalist_option.html'

  def __init__(self, attrs=None):
    self._has_error = False

    if attrs is not None:
      self.input_type = attrs.get('type', self.input_type)
      self.input_list = attrs.pop('list', self.input_list)
      self.use_dataset_attr = attrs.pop('use-dataset', self.use_dataset_attr)
    super().__init__(attrs)

  def get_context(self, name, value, attrs):
    context = super().get_context(name, value, attrs)
    context['widget']['has_error'] = self._has_error
    context['widget']['initial'] = value
    context['widget']['type'] = self.input_type
    context['widget']['id'] = self.input_list if self.input_list else f'{name}_datalist'
    context['widget']['use_dataset'] = self.use_dataset()

    return context

  def use_dataset(self):
    return bool(self.use_dataset_attr)

  @property
  def has_error(self):
    raise AttributeError('Invalid data access')
  @has_error.setter
  def has_error(self, value):
    self._has_error = True

class DropdownWithInput(forms.Select):
  input_type = 'text'
  template_name = 'widgets/custom_dropdown.html'
  option_template_name = 'widgets/custom_dropdown_option.html'

  def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
    option = super().create_option(name, value, label, selected, index, subindex, attrs)
    option['attrs']['data-value'] = value

    return option

  def get_context(self, name, value, attrs):
    context = super().get_context(name, value, attrs)
    context['widget']['type'] = self.input_type
    context['widget']['initial'] = ','.join(value) if isinstance(value, list) else value
    context['widget']['dropdown_id'] = f'{name}_dropdown'

    return context

class DatalistField(forms.ChoiceField):
  widget = Datalist

class ModelDatalistField(forms.ModelChoiceField):
  widget = Datalist

  def __init__(self, queryset, *, widget=None, **kwargs):
    widget = widget or self.widget
    super().__init__(queryset, widget=widget, **kwargs)

class DropdownField(forms.MultipleChoiceField):
  widget = DropdownWithInput

  def to_python(self, value):
    if isinstance(value, (list, tuple)) and any([val in self.empty_values for val in value]) and self.initial:
      out = self.initial
    else:
      out = super().to_python(value)

    return out

class CustomRadioSelect(forms.RadioSelect):
  input_class = ''
  label_class = ''
  template_name = 'widgets/custom_radio.html'
  option_template_name = 'widgets/custom_radio_option.html'

  def __init__(self, attrs=None):
    if attrs is not None:
      self.input_class = attrs.pop('input-class', self.input_class)
      self.label_class = attrs.pop('label-class', self.label_class)
    super().__init__(attrs)

  def create_option(self, *args, **kwargs):
    options = super().create_option(*args, **kwargs)
    options['input_class'] = self.input_class
    options['label_class'] = self.label_class

    return options