import pytest
from stock import models
from stock.management.commands import exec_job
from app_tests import factories, BaseTestUtils

@pytest.mark.stock
@pytest.mark.django_db
class TestExecJob(BaseTestUtils):
  @pytest.fixture(scope='class')
  def get_dummy_stock_data(self, django_db_blocker):
    with django_db_blocker.unblock():
      industry = factories.IndustryFactory()
      stocks = factories.StockFactory.create_batch(202, industry=industry)

    return stocks

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
  def test_call_background_job(self, mocker, get_dummy_stock_data, num, count):
    stocks = get_dummy_stock_data
    queryset = models.Stock.objects.filter(pk__in=self.get_pks(stocks[:num]))
    # Setup mock
    mocker.patch('stock.models.Stock.objects.select_targets', return_value=queryset)
    func_mock = mocker.patch('stock.management.commands.exec_job.update_stock_records.apply_async', return_value=None)
    print_mock = mocker.patch('stock.management.commands.exec_job.print', return_value=None)
    command = exec_job.Command()
    command.handle()

    assert func_mock.call_count == num
    assert print_mock.call_count == count