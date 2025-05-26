from app_tests.account_tests import factories as account_factories
from app_tests.stock_tests import factories as stock_factories

UserFactory = account_factories.UserFactory
IndustryFactory = stock_factories.IndustryFactory
StockFactory = stock_factories.StockFactory
CashFactory = stock_factories.CashFactory
PurchasedStockFactory = stock_factories.PurchasedStockFactory
SnapshotFactory = stock_factories.SnapshotFactory