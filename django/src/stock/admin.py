from django.contrib import admin
from django.utils.translation import gettext_lazy
from .models import Industry, Stock, Cash, PurchasedStock, Snapshot

@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin):
  model = Industry
  fields = ['name', 'is_defensive']
  list_display = ('name', 'is_defensive')
  list_filter = ('is_defensive',)
  search_fields = ('name', 'is_defensive')
  ordering = ('pk',)

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
  model = Stock
  fields = ['code', 'name', 'industry', 'price', 'dividend', 'per', 'pbr', 'eps']
  list_display = ('code', 'name', 'industry', 'price', 'dividend')
  list_filter = ('industry', 'dividend')
  search_fields = ('code', 'name', 'industry')
  ordering = ('pk',)

@admin.register(Cash)
class CashAdmin(admin.ModelAdmin):
  model = Cash
  fields = ['user', 'balance', 'registered_date']
  list_display = ('user', 'balance', 'registered_date')
  list_filter = ('user',)
  search_fields = ('user', 'balance', 'registered_date')
  ordering = ('-registered_date', 'balance')

@admin.register(PurchasedStock)
class PurchasedStockAdmin(admin.ModelAdmin):
  model = PurchasedStock
  fields = ['user', 'stock', 'purchase_date', 'count']
  list_display = ('user', 'stock', 'purchase_date', 'count')
  list_filter = ('user',)
  search_fields = ('user', 'purchase_date')
  ordering = ('-purchase_date', 'stock__code')

@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
  model = Snapshot
  fields = ['user', 'title', 'detail', 'created_at']
  list_display = ('user', 'title', 'created_at')
  list_filter = ('user',)
  search_fields = ('user', 'created_at')
  ordering = ('-created_at',)
