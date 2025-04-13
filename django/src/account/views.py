from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils.translation import gettext_lazy
from . import forms

class Index(TemplateView):
  template_name = 'account/index.html'

class LoginPage(LoginView):
  template_name = 'account/login.html'
  redirect_authenticated_user = True
  form_class = forms.LoginForm

class LogoutPage(LogoutView):
  template_name = 'account/index.html'