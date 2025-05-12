from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import View
from utils.views import (
  CreateViewBasedOnUser,
  UpdateViewBasedOnUser,
  CustomDeleteView,
  DjangoBreadcrumbsMixin,
)
from account.views import Index
from . import models, forms

class Dashboard(LoginRequiredMixin, ListView, DjangoBreadcrumbsMixin):
  model = models.Snapshot
  template_name = 'stock/dashboard.html'
  context_object_name = 'snapshots'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:dashboard',
    title=gettext_lazy('Dashboard'),
    parent_view_class=Index,
  )

  def get_queryset(self):
    user = self.request.user
    queryset = user.snapshots.all()

    return queryset

class StockAjaxResponse(View):
  raise_exception = True
  http_method_names = ['get']

  def get(self, request, *args, **kwargs):
    data = models.Stock.get_choices_as_list()
    response = JsonResponse({'qs': data})

    return response

class ListCash(LoginRequiredMixin, ListView, DjangoBreadcrumbsMixin):
  model = models.Cash
  template_name = 'stock/cashes.html'
  paginate_by = 10
  context_object_name = 'cashes'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:list_cash',
    title=gettext_lazy('Cash list'),
    parent_view_class=Index,
  )

  def get_queryset(self):
    user = self.request.user
    queryset = user.cashes.all()

    return queryset

class RegisterCash(CreateViewBasedOnUser, DjangoBreadcrumbsMixin):
  model = models.Cash
  form_class = forms.CashForm
  template_name = 'stock/cash_form.html'
  success_url = reverse_lazy('stock:list_cash')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:register_cash',
    title=gettext_lazy('Register cash'),
    parent_view_class=ListCash,
  )

class UpdateCash(UpdateViewBasedOnUser, DjangoBreadcrumbsMixin):
  model = models.Cash
  form_class = forms.CashForm
  template_name = 'stock/cash_form.html'
  success_url = reverse_lazy('stock:list_cash')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:update_cash',
    title=gettext_lazy('Update cash'),
    parent_view_class=ListCash,
    url_keys=['pk'],
  )

class DeleteCash(CustomDeleteView, DjangoBreadcrumbsMixin):
  model = models.Cash
  success_url = reverse_lazy('stock:list_cash')

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

class UpdatePurchasedStock(UpdateViewBasedOnUser, DjangoBreadcrumbsMixin):
  model = models.PurchasedStock
  form_class = forms.PurchasedStockForm
  template_name = 'stock/purchased_stock_form.html'
  success_url = reverse_lazy('stock:list_purchased_stock')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:update_purchased_stock',
    title=gettext_lazy('Update purchsed stock'),
    parent_view_class=ListPurchasedStock,
    url_keys=['pk'],
  )

  def get_form(self):
    form = super().get_form()
    form.update_queryset(self.kwargs['pk'])

    return form

class DeletePurchasedStock(CustomDeleteView, DjangoBreadcrumbsMixin):
  model = models.PurchasedStock
  success_url = reverse_lazy('stock:list_purchased_stock')

class ListSnapshot(LoginRequiredMixin, ListView, DjangoBreadcrumbsMixin):
  model = models.Snapshot
  template_name = 'stock/snapshots.html'
  paginate_by = 10
  context_object_name = 'snapshots'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:list_snapshot',
    title=gettext_lazy('Snapshot list'),
    parent_view_class=Index,
  )

  def get_queryset(self):
    user = self.request.user
    queryset = user.snapshots.all()

    return queryset

class RegisterSnapshot(CreateViewBasedOnUser, DjangoBreadcrumbsMixin):
  model = models.Snapshot
  form_class = forms.SnapshotForm
  template_name = 'stock/snapshot_form.html'
  success_url = reverse_lazy('stock:list_snapshot')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:register_snapshot',
    title=gettext_lazy('Register snapshot'),
    parent_view_class=ListSnapshot,
  )

class UpdateSnapshot(UpdateViewBasedOnUser, DjangoBreadcrumbsMixin):
  model = models.Snapshot
  form_class = forms.SnapshotForm
  template_name = 'stock/snapshot_form.html'
  success_url = reverse_lazy('stock:list_snapshot')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:update_snapshot',
    title=gettext_lazy('Update snapshot'),
    parent_view_class=ListSnapshot,
    url_keys=['pk'],
  )

class DeleteSnapshot(CustomDeleteView):
  model = models.Snapshot
  success_url = reverse_lazy('stock:list_snapshot')

class AjaxUpdateAllSnapshots(View):
  raise_exception = True
  http_method_names = ['post']

  def post(self, request, *args, **kwargs):
    try:
      models.Snapshot.save_all(request.user)
      data = {'status': True}
    except:
      data = {'status': False}
    response = JsonResponse(data)

    return response