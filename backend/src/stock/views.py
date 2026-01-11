from django.views.generic import (
  TemplateView,
  ListView,
  UpdateView,
  DeleteView,
  DetailView,
  View,
  FormView,
)
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils.translation import gettext_lazy
from django.http import JsonResponse, StreamingHttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy, reverse
from django_celery_beat.models import PeriodicTask
from utils.views import (
  BaseCreateUpdateView,
  CreateViewBasedOnUser,
  UpdateViewBasedOnUser,
  CustomDeleteView,
  DjangoBreadcrumbsMixin,
)
from account.views import Index
from . import models, forms
from utils.models import streaming_csv_file

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

class InvestmentHistory(Dashboard):
  template_name = 'stock/investment_history.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:investment_history',
    title=gettext_lazy('Investment history'),
    parent_view_class=Index,
  )

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
  paginate_by = 24
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
  paginate_by = 20
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
  paginate_by = 36
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

class IsOwnSnapshotTask(UserPassesTestMixin):
  def test_func(self):
    instance = self.get_object()
    user = self.request.user
    queryset = models.Snapshot.get_queryset_from_periodic_task(user, pk=instance.pk)
    is_valid = queryset.exists()

    return is_valid

class ListPeriodicTaskForSnapshot(LoginRequiredMixin, ListView, DjangoBreadcrumbsMixin):
  model = PeriodicTask
  template_name = 'stock/periodic_tasks_for_snapshot.html'
  paginate_by = 36
  context_object_name = 'tasks'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:list_snapshot_task',
    title=gettext_lazy('Periodic task list for snapshot'),
    parent_view_class=Index,
  )

  def get_queryset(self):
    user = self.request.user
    queryset = models.Snapshot.get_queryset_from_periodic_task(user)

    return queryset

class RegisterPeriodicTaskForSnapshot(CreateViewBasedOnUser, DjangoBreadcrumbsMixin):
  model = PeriodicTask
  form_class = forms.PeriodicTaskForSnapshotForm
  template_name = 'stock/periodic_task_for_snapshot_form.html'
  success_url = reverse_lazy('stock:list_snapshot_task')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:register_snapshot_task',
    title=gettext_lazy('Register periodic task for snapshot'),
    parent_view_class=ListPeriodicTaskForSnapshot,
  )

class UpdatePeriodicTaskForSnapshot(BaseCreateUpdateView, IsOwnSnapshotTask, UpdateView, DjangoBreadcrumbsMixin):
  model = PeriodicTask
  form_class = forms.PeriodicTaskForSnapshotForm
  template_name = 'stock/periodic_task_for_snapshot_form.html'
  success_url = reverse_lazy('stock:list_snapshot_task')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:update_snapshot_task',
    title=gettext_lazy('Update periodic task for snapshot'),
    parent_view_class=ListPeriodicTaskForSnapshot,
    url_keys=['pk'],
  )

  def get_form(self, form_class=None):
    form = super().get_form(form_class=form_class)
    form.update_initial(self.object)

    return form

class DeletePeriodicTaskForSnapshot(LoginRequiredMixin, IsOwnSnapshotTask, DeleteView):
  raise_exception = True
  http_method_names = ['post']
  model = PeriodicTask
  success_url = reverse_lazy('stock:list_snapshot_task')

class ListStock(LoginRequiredMixin, FormView, ListView, DjangoBreadcrumbsMixin):
  raise_exception = True
  http_method_names = ['get']
  model = models.Stock
  template_name = 'stock/stocks.html'
  form_class = forms.StockSearchForm
  paginate_by = 150
  context_object_name = 'stocks'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:list_stock',
    title=gettext_lazy('Stock list'),
    parent_view_class=Index,
  )

  def get_queryset(self):
    params = self.request.GET.copy() or {}
    # Create form
    self.form = self.form_class(data=params)
    queryset = self.form.get_queryset_with_condition()

    return queryset

  def get_context_data(self, **kwargs):
    is_secure = getattr(settings, 'IS_SECURE_COOKIE', True)
    context = super().get_context_data(**kwargs)
    context['form'] = self.form
    context['download_form'] = forms.StockDownloadForm()
    context['is_secure'] = 'Secure' if is_secure else ''

    return context

class DownloadStockPage(LoginRequiredMixin, FormView, DjangoBreadcrumbsMixin):
  raise_exception = True
  http_method_names = ['post']
  form_class = forms.StockDownloadForm

  def form_valid(self, form):
    kwargs = form.create_response_kwargs()
    # Create response
    max_age = getattr(settings, 'CSV_DOWNLOAD_MAX_AGE', 5 * 60)
    is_secure = getattr(settings, 'IS_SECURE_COOKIE', True)
    filename = kwargs['filename']
    response = StreamingHttpResponse(
      streaming_csv_file(kwargs['rows'], header=kwargs['header']),
      content_type='text/csv;charset=UTF-8',
      headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
    response.set_cookie(
      'stock_download_status',
      value='completed',
      max_age=max_age,
      secure=is_secure,
    )

    return response

  def form_invalid(self, form):
    query_string = form.get_query_string()
    url = '{}?{}'.format(reverse('stock:list_stock'), query_string)
    response = HttpResponseRedirect(url)

    return response

class ExplanationPage(LoginRequiredMixin, TemplateView, DjangoBreadcrumbsMixin):
  template_name = 'stock/explanation.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='stock:explanation',
    title=gettext_lazy('Explanation'),
    parent_view_class=Index,
  )