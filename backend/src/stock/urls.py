from django.urls import path
from . import views

app_name = 'stock'

urlpatterns = [
  path('', views.Dashboard.as_view(), name='dashboard'),
  path('investment-history', views.InvestmentHistory.as_view(), name='investment_history'),
  path('ajax/stock', views.StockAjaxResponse.as_view(), name='ajax_stock'),
  # Cash
  path('list/cashes', views.ListCash.as_view(), name='list_cash'),
  path('register/cash', views.RegisterCash.as_view(), name='register_cash'),
  path('update/cash/<int:pk>', views.UpdateCash.as_view(), name='update_cash'),
  path('delete/cash/<int:pk>', views.DeleteCash.as_view(), name='delete_cash'),
  # Purchased stock
  path('list/purchased-stocks', views.ListPurchasedStock.as_view(), name='list_purchased_stock'),
  path('register/purchased-stock', views.RegisterPurchasedStock.as_view(), name='register_purchased_stock'),
  path('update/purchased-stock/<int:pk>', views.UpdatePurchasedStock.as_view(), name='update_purchased_stock'),
  path('delete/purchased-stock/<int:pk>', views.DeletePurchasedStock.as_view(), name='delete_purchased_stock'),
  # Snapshot
  path('list/snapshots', views.ListSnapshot.as_view(), name='list_snapshot'),
  path('register/snapshot', views.RegisterSnapshot.as_view(), name='register_snapshot'),
  path('update/snapshot/<int:pk>', views.UpdateSnapshot.as_view(), name='update_snapshot'),
  path('delete/snapshot/<int:pk>', views.DeleteSnapshot.as_view(), name='delete_snapshot'),
  path('update/all-snapshots', views.AjaxUpdateAllSnapshots.as_view(), name='update_all_snapshots'),
  # Stock
  path('list/stocks', views.ListStock.as_view(), name='list_stock'),
  path('explanation', views.ExplanationPage.as_view(), name='explanation'),
]