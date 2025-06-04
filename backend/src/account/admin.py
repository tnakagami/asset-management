from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy
from .models import User

class CustomUserChangeForm(UserChangeForm):
  class Meta:
    model = User
    fields = '__all__'

class CustomUserCreationForm(UserCreationForm):
  class Meta:
    model = User
    fields = ('username', 'email', 'screen_name',)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
  fieldsets = (
    (None, {'fields': ('username', 'email', 'screen_name', 'password')}),
    (gettext_lazy('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    (gettext_lazy('Important dates'), {'fields': ('last_login', 'date_joined')}),
  )
  add_fieldsets = (
    (None, {
      'classes': ('wide',),
      'fields': ('username', 'email', 'password1', 'password2', 'screen_name',),
    }),
  )

  form = CustomUserChangeForm
  add_form = CustomUserCreationForm
  list_display = ('username', 'email', 'screen_name', 'is_staff')
  list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
  search_fields = ('username', 'email', 'screen_name')
  ordering = ('id',)