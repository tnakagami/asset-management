import pytest
from django.contrib.admin.sites import AdminSite
from stock import models, admin
from . import factories

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'lang',
  'exact',
], [
  ('en', 'hoge-en'),
  ('ja', 'fuga-ja'),
  ('fr', ''),
], ids=[
  'industry-English-ver',
  'industry-Japanese-ver',
  'industry-French-ver',
])
def test_localized_name_of_industry_admin(mocker, settings, lang, exact):
  mocker.patch('stock.models.get_language', return_value=lang)
  settings.LANGUAGE_CODE = 'ge'
  instance = admin.IndustryAdmin(model=models.Industry, admin_site=AdminSite())
  industry = factories.IndustryFactory.build()
  instance.save_model(obj=industry, request=None, form=None, change=None)
  _ = factories.LocalizedIndustryFactory(name='hoge-en', language_code='en', industry=industry)
  _ = factories.LocalizedIndustryFactory(name='fuga-ja', language_code='ja', industry=industry)

  assert instance.localized_name(industry) == exact

@pytest.mark.stock
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'lang',
  'exact',
], [
  ('en', 'hoge-en'),
  ('ja', 'fuga-ja'),
  ('fr', ''),
], ids=[
  'stock-English-ver',
  'stock-Japanese-ver',
  'stock-French-ver',
])
def test_localized_name_of_stock_admin(mocker, settings, lang, exact):
  mocker.patch('stock.models.get_language', return_value=lang)
  settings.LANGUAGE_CODE = 'ge'
  instance = admin.StockAdmin(model=models.Stock, admin_site=AdminSite())
  industry = factories.IndustryFactory()
  stock = factories.StockFactory.build(industry=industry)
  instance.save_model(obj=stock, request=None, form=None, change=None)
  _ = factories.LocalizedStockFactory(name='hoge-en', language_code='en', stock=stock)
  _ = factories.LocalizedStockFactory(name='fuga-ja', language_code='ja', stock=stock)

  assert instance.localized_name(stock) == exact