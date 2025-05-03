from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy
from django.urls import reverse
from utils.views import IsOwner, DjangoBreadcrumbsMixin
from . import models, forms

class Index(TemplateView, DjangoBreadcrumbsMixin):
  template_name = 'account/index.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:index',
    title=gettext_lazy('Home'),
  )

class LoginPage(LoginView, DjangoBreadcrumbsMixin):
  template_name = 'account/login.html'
  redirect_authenticated_user = True
  form_class = forms.LoginForm
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:login',
    title=gettext_lazy('Login'),
    parent_view_class=Index,
  )

class LogoutPage(LogoutView):
  template_name = 'account/index.html'

class UserProfilePage(LoginRequiredMixin, IsOwner, DetailView, DjangoBreadcrumbsMixin):
  raise_exception = True
  model = models.User
  template_name = 'account/user_profile.html'
  context_object_name = 'owner'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:user_profile',
    title=gettext_lazy('User profile'),
    parent_view_class=Index,
    url_keys=['pk'],
  )

class UpdateUserProfile(LoginRequiredMixin, IsOwner, UpdateView, DjangoBreadcrumbsMixin):
  raise_exception = True
  model = models.User
  form_class = forms.UserProfileForm
  template_name = 'account/profile_form.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:update_profile',
    title=gettext_lazy('Update user profile'),
    parent_view_class=UserProfilePage,
    url_keys=['pk'],
  )

  def get_success_url(self):
    return reverse('account:user_profile', kwargs={'pk': self.kwargs['pk']})