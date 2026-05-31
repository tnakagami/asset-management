from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy
from stock.models import Stock
from . import run_stock_task

class Command(BaseCommand):
  def add_arguments(self, parser):
    parser.add_argument(
      '--stock-codes',
      dest='codes',
      type=str,
      nargs='+',
      required=True,
      help=gettext_lazy('Target stock codes (multiple codes may be specified, separated by spaces)'),
    )

  def handle(self, *args, **options):
    # Get the argument
    input_codes = {code.strip() for code in options.get('codes') if code.strip()}
    # Collect stock instances
    stocks = Stock.objects.filter(code__in=input_codes)
    total = stocks.count()

    # Pre-process
    if total <= 0:
      err_msg = gettext_lazy('Error: No valid code has been specified.')
      self.stdout.write(self.style.ERROR(str(err_msg)))
      return

    # Main process
    for idx, instance in enumerate(stocks, 1):
      run_stock_task(idx, total, instance)

    # Post process
    message = gettext_lazy('All jobs have been started(total: %(total)s).') % {'total': total}
    self.stdout.write(self.style.SUCCESS(str(message)))