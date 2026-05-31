from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy
from stock.models import Stock
from . import run_stock_task
import random

class Command(BaseCommand):
  def handle(self, *args, **options):
    random.seed()
    queryset = Stock.objects.select_targets().order_by('?')
    total = queryset.count()

    # Main process
    for idx, instance in enumerate(queryset, 1):
      run_stock_task(idx, total, instance)

      if (idx % 100) == 0:
        message = gettext_lazy('Processing status: %(idx)s / %(total)s started') % {'idx': idx, 'total': total}
        self.stdout.write(str(message))

    # Post process
    message = gettext_lazy('All jobs have been started(total: %(total)s).') % {'total': total}
    self.stdout.write(self.style.SUCCESS(str(message)))