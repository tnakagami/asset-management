import pytest
from stock.management.commands import exec_job
from . import factories

@pytest.mark.stock
@pytest.mark.django_db
@pytest.mark.parametrize([
  'num',
  'count',
], [
  (99,  0),
  (100, 1),
  (101, 1),
  (199, 1),
  (200, 2),
  (201, 2),
], ids=lambda val: f'v{val}')
def test_call_background_job(mocker, num, count):
  industry = factories.IndustryFactory()
  _ = factories.StockFactory.create_batch(num, industry=industry)

  func_mock = mocker.patch('stock.management.commands.exec_job.update_stock_records.apply_async', return_value=None)
  print_mock = mocker.patch('stock.management.commands.exec_job.print', return_value=None)
  command = exec_job.Command()
  command.handle()

  assert func_mock.call_count == num
  assert print_mock.call_count == count