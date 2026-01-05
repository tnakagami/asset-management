from django.urls import reverse
from django.utils.translation import gettext_lazy
from django.views.generic import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from crumbles import CrumblesViewMixin, CrumbleDefinition
from operator import attrgetter, methodcaller

class IsOwner(UserPassesTestMixin):
  owner_name = 'user'

  def test_func(self):
    instance = self.get_object()
    owner = getattr(instance, self.owner_name, instance)
    is_valid = owner.pk == self.request.user.pk

    return is_valid

class BaseCreateUpdateView(LoginRequiredMixin):
  raise_exception = True

  def get_form_kwargs(self, *args, **kwargs):
    kwargs = super().get_form_kwargs(*args, **kwargs)
    kwargs['user'] = self.request.user

    return kwargs

class CreateViewBasedOnUser(BaseCreateUpdateView, CreateView):
  pass

class UpdateViewBasedOnUser(BaseCreateUpdateView, IsOwner, UpdateView):
  pass

class CustomDeleteView(LoginRequiredMixin, IsOwner, DeleteView):
  raise_exception = True
  http_method_names = ['post']
  model = None
  success_url = None

class DjangoBreadcrumbsMixin(CrumblesViewMixin):
  def url_resolve(self, *args, **kwargs):
    return reverse(*args, **kwargs)

  @classmethod
  def get_target_crumbles(cls, url_name, title, parent_view_class=None, url_keys=None):
    if parent_view_class is None:
      # In the case of getting current crumbles
      crumbles = (
        CrumbleDefinition(url_name=url_name, title=title),
      )
    else:
      _kwargs = dict([(key, attrgetter(key)) for key in url_keys]) if url_keys is not None else {}
      # In the case of including parent crumbles
      crumbles = parent_view_class.crumbles + (
        CrumbleDefinition(url_name=url_name, url_resolve_kwargs=_kwargs, title=title),
      )

    return crumbles
