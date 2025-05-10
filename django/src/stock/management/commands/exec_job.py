from django.core.management.base import BaseCommand
from stock.models import Stock
from stock.tasks import update_stock_records
import random

class Command(BaseCommand):
  def handle(self, *args, **options):
    random.seed()
    queryset = Stock.objects.all().order_by('?')
    total = queryset.count()

    for idx, instance in enumerate(queryset, 1):
      kwargs = {
        'idx': idx,
        'pk': instance.pk,
        'code': instance.code,
        'total': total,
      }
      update_stock_records.apply_async(kwargs=kwargs)