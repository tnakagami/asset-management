import pytest
from stock.management.commands import exec_job
from . import factories

@pytest.mark.stock
@pytest.mark.django_db
def test_call_background_job(mocker):
  num = 16
  _ = factories.StockFactory.create_batch(num)

  func_mock = mocker.patch('stock.management.commands.exec_job.update_stock_records.apply_async', return_value=None)
  command = exec_job.Command()
  command.handle()

  assert func_mock.call_count == num