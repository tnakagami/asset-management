from django import forms
from .widgets import ModelDatalistField
from .models import empty_qs

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

class BaseModelDatalistForm(forms.BaseForm):
  field_class = ModelDatalistField

  class Meta:
    datalist_fields = []
    datalist_kwargs = {}

  def __init__(self, *args, field_class=None, **kwargs):
    super().__init__(*args, **kwargs)

    _meta = getattr(self, 'Meta', None)
    field_class = field_class or self.field_class
    datalist_fields = getattr(_meta, 'datalist_fields', [])
    datalist_kwargs = getattr(_meta, 'datalist_kwargs', {})
    widgets = getattr(_meta, 'widgets', {})
    dynamic_fields = {}
    # Create fields dynamically
    for field_name in datalist_fields:
      widget = widgets.get(field_name, None)
      options = datalist_kwargs.get(field_name, {'queryset': empty_qs})
      dynamic_fields[field_name] = field_class(widget=widget, **options)
    # Update declared_fields
    self.declared_fields.update(dynamic_fields)
    self._extra_datalist_fields = [item for item in datalist_fields]
    # Update fields data
    self.fields.update(self.declared_fields)

  @property
  def datalist_template_name(self):
    return 'renderer/custom_datalist_javascript.html'

  @property
  def datalist_ids(self):
    related_fields = [
      self.fields[field_name]
      for field_name in self._extra_datalist_fields if self.fields[field_name].widget.use_dataset()
    ]
    datalist_ids = [field.widget.attrs['id'] for field in related_fields]

    return datalist_ids