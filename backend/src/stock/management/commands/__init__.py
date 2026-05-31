from stock.tasks import update_stock_records

def run_stock_task(idx, total, stock):
  kwargs = {
    'idx': idx,
    'pk': stock.pk,
    'code': stock.code,
    'total': total,
  }
  update_stock_records.apply_async(kwargs=kwargs)

__all__ = [
  'run_stock_task',
]