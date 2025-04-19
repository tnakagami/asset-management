from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy
from . import models

class LoginForm(AuthenticationForm):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    for field in self.fields.values():
      field.widget.attrs['class'] = 'form-control'

class UserProfileForm(forms.ModelForm):
  class Meta:
    model = models.User
    fields = ('screen_name', )
    widgets = {
      'screen_name': forms.TextInput(attrs={
        'placeholder': gettext_lazy('Enter the screen name'),
        'class': 'form-control',
      })
    }