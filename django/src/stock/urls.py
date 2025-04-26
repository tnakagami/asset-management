from django.urls import path
from . import views

app_name = 'stock'

urlpatterns = [
  path('', views.Dashboard.as_view(), name='dashboard'),
  path('list/purchased-stocks', views.ListPurchasedStock.as_view(), name='list_purchased_stock'),
  path('register/purchased-stocks', views.RegisterPurchasedStock.as_view(), name='register_purchased_stock'),
]