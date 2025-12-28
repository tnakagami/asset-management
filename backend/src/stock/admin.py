from django.contrib import admin
from django.utils.translation import gettext_lazy
from .models import (
  LocalizedIndustry,
  Industry,
  LocalizedStock,
  Stock,
  Cash,
  PurchasedStock,
  Snapshot,
)

@admin.register(LocalizedIndustry)
class LocalizedIndustryAdmin(admin.ModelAdmin):
  model = LocalizedIndustry
  fields = ['name', 'language_code', 'industry']
  list_display = ('name', 'language_code')
  list_filter = ('language_code',)
  search_fields = ('name', 'language_code')
  ordering = ('pk',)

@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin):
  model = Industry
  fields = ['is_defensive']
  readonly_fields = ['localized_name']
  list_display = ('localized_name', 'is_defensive')
  list_filter = ('is_defensive',)
  search_fields = ('localized_name', 'is_defensive')
  ordering = ('pk',)

  @admin.display(description=gettext_lazy('Name'))
  def localized_name(self, instance):
    return instance.get_name()

@admin.register(LocalizedStock)
class LocalizedStockAdmin(admin.ModelAdmin):
  model = LocalizedStock
  fields = ['name', 'language_code', 'stock']
  list_display = ('name', 'language_code', 'stock')
  list_filter = ('language_code',)
  search_fields = ('name', 'language_code')
  ordering = ('pk',)

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
  model = Stock
  fields = ['code', 'industry', 'price', 'dividend', 'per', 'pbr', 'eps', 'bps', 'roe', 'er']
  readonly_fields = ['localized_name']
  list_display = ('code', 'localized_name', 'industry', 'price', 'dividend')
  list_filter = ('industry', 'dividend')
  search_fields = ('code', 'localized_name', 'industry')
  ordering = ('code',)

  @admin.display(description=gettext_lazy('Name'))
  def localized_name(self, instance):
    return instance.get_name()

@admin.register(Cash)
class CashAdmin(admin.ModelAdmin):
  model = Cash
  fields = ['user', 'balance', 'registered_date']
  list_display = ('user', 'balance', 'registered_date')
  list_filter = ('user',)
  search_fields = ('user__username', 'user__screen_name', 'balance', 'registered_date')
  ordering = ('-registered_date', 'balance')

@admin.register(PurchasedStock)
class PurchasedStockAdmin(admin.ModelAdmin):
  model = PurchasedStock
  fields = ['user', 'stock', 'purchase_date', 'count']
  list_display = ('user', 'stock', 'purchase_date', 'count')
  list_filter = ('user',)
  search_fields = ('user__username', 'user__screen_name', 'stock__code', 'purchase_date')
  ordering = ('-purchase_date', 'stock__code')

@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
  model = Snapshot
  fields = ['user', 'title', 'detail', 'priority', 'start_date', 'end_date', 'created_at']
  list_display = ('user', 'title', 'priority', 'start_date', 'end_date')
  list_filter = ('user',)
  search_fields = ('user__username', 'user__screen_name', 'priority', 'start_date', 'end_date')
  ordering = ('priority', '-created_at',)
