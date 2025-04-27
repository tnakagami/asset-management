from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy
from django.urls import reverse_lazy
from utils.views import (
  CreateViewBasedOnUser,
  CustomDeleteView,
  DjangoBreadcrumbsMixin,
)
from account.views import Index
from . import models, forms

class Dashboard(LoginRequiredMixin, TemplateView, DjangoBreadcrumbsMixin):
  template_name = 'stock/dashboard.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:dashboard',
    title=gettext_lazy('Dashboard'),
    parent_view_class=Index,
  )

class ListPurchasedStock(LoginRequiredMixin, ListView, DjangoBreadcrumbsMixin):
  model = models.PurchasedStock
  template_name = 'stock/purchased_stocks.html'
  paginate_by = 10
  context_object_name = 'pstocks'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:list_purchased_stock',
    title=gettext_lazy('Purchsed stock list'),
    parent_view_class=Index,
  )

  def get_queryset(self):
    user = self.request.user
    queryset = user.purchased_stocks.all()

    return queryset

class RegisterPurchasedStock(CreateViewBasedOnUser, DjangoBreadcrumbsMixin):
  model = models.PurchasedStock
  form_class = forms.PurchasedStockForm
  template_name = 'stock/purchased_stock_form.html'
  success_url = reverse_lazy('stock:list_purchased_stock')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:register_purchased_stock',
    title=gettext_lazy('Register purchsed stock'),
    parent_view_class=ListPurchasedStock,
  )

class DeletePurchasedStock(CustomDeleteView, DjangoBreadcrumbsMixin):
  model = models.PurchasedStock
  success_url = reverse_lazy('stock:list_purchased_stock')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:update_purchased_stock',
    title=gettext_lazy('Update purchsed stock'),
    parent_view_class=ListPurchasedStock,
    url_keys=['pk'],
  )