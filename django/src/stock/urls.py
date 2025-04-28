from django.urls import path
from . import views

app_name = 'stock'

urlpatterns = [
  path('', views.Dashboard.as_view(), name='dashboard'),
  # Cash
  path('list/cashes', views.ListCash.as_view(), name='list_cash'),
  path('register/cash', views.RegisterCash.as_view(), name='register_cash'),
  path('delete/cash/<int:pk>', views.DeleteCash.as_view(), name='delete_cash'),
  # Purchased stock
  path('list/purchased-stocks', views.ListPurchasedStock.as_view(), name='list_purchased_stock'),
  path('register/purchased-stock', views.RegisterPurchasedStock.as_view(), name='register_purchased_stock'),
  path('delete/purchased-stock/<int:pk>', views.DeletePurchasedStock.as_view(), name='delete_purchased_stock'),
]