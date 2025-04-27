from django import forms
from .widgets import ModelDatalistField

class ModelFormBasedOnUser(forms.ModelForm):
  template_name = 'renderer/custom_form.html'

  def __init__(self, user, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.user = user

  def save(self, *args, **kwargs):
    instance = super().save(commit=False)
    instance.user = self.user
    instance.save()

    return instance

class ModelDatalistFormMixin(forms.BaseForm):
  class Meta:
    datalist_fields = []
    datalist_kwargs = {}

  def __init__(self, *args, **kwargs):
    _meta = getattr(self, 'Meta', None)
    datalist_fields = getattr(_meta, 'datalist_fields', [])
    datalist_kwargs = getattr(_meta, 'datalist_kwargs', {})
    widgets = getattr(_meta, 'widgets', {})
    dynamic_fields = {}
    # Create fields dynamically
    for field_name in datalist_fields:
      widget = widgets[field_name]
      options = datalist_kwargs[field_name]
      dynamic_fields[field_name] = ModelDatalistField(widget=widget, **options)
    # Update declared_fields
    self.declared_fields.update(dynamic_fields)
    self._extra_datalist_fields = [item for item in datalist_fields]
    # Call constractor of parent class
    super().__init__(*args, **kwargs)
    # Update fields data
    self.fields.update(self.declared_fields)

  @property
  def datalist_template_name(self):
    return 'renderer/custom_datalist_javascript.html'

  @property
  def datalist_ids(self):
    extra_attrs = [self.fields[field_name].widget.attrs for field_name in self._extra_datalist_fields]
    datalist_ids = [attrs['id'] for attrs in extra_attrs]

    return datalist_ids