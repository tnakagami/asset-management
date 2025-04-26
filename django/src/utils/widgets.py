from django import forms

class Datalist(forms.Select):
  input_type = 'text'
  input_list = ''
  use_dataset_attr = False
  template_name = 'widgets/custom_datalist.html'
  option_template_name = 'widgets/custom_datalist_option.html'

  def __init__(self, attrs=None):
    if attrs is not None:
      self.input_list = attrs.pop('list', self.input_list)
      self.use_dataset_attr = attrs.pop('use-dataset', self.use_dataset_attr)
    super().__init__(attrs)

  def get_context(self, name, value, attrs):
    context = super().get_context(name, value, attrs)
    context['widget']['type'] = 'text'
    context['widget']['id'] = self.input_list if self.input_list else f'{name}_datalist'
    context['widget']['use_dataset'] = bool(self.use_dataset_attr)

    return context

class DatalistField(forms.ChoiceField):
  widget = Datalist

class ModelDatalistField(forms.ModelChoiceField):
  widget = Datalist

  def __init__(self, queryset, *, widget=None, **kwargs):
    widget = widget or self.widget
    super().__init__(queryset, widget=widget, **kwargs)