from django.urls import reverse
from django.utils.translation import gettext_lazy
from crumbles import CrumblesViewMixin, CrumbleDefinition
from operator import attrgetter, methodcaller

class DjangoBreadcrumbsMixin(CrumblesViewMixin):
  def url_resolve(self, *args, **kwargs):
    return reverse(*args, **kwargs)

def get_target_crumbles(url_name, title, parent_view_class=None, url_keys=None):
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