#!/bin/bash

readonly APP_ROOT_DIR=/opt/app
readonly MANAGE_PATH=$(find ${APP_ROOT_DIR} -name "manage.py")
readonly BASE_DIR=${APP_ROOT_DIR}/stock/fixtures

echo Create db_industry.yaml to ${BASE_DIR} based on database.
{
  python ${MANAGE_PATH} dumpdata --format=yaml stock.industry
  python ${MANAGE_PATH} dumpdata --format=yaml stock.localizedindustry
} > ${BASE_DIR}/db_industry.yaml

echo Create db_stock.yaml to ${BASE_DIR} based on database.
{
  python ${MANAGE_PATH} dumpdata --format=yaml stock.stock | \
  sed -E -e "s|code: '(.*)'|code: \1|g" | \
  sed -e "s|price: '.*'|price: 0|g" \
      -e "s|dividend: '.*'|dividend: 0|g" \
      -e "s|per: '.*'|per: 0|g" \
      -e "s|pbr: '.*'|pbr: 0|g" \
      -e "s|eps: '.*'|eps: 0|g" \
      -e "s|bps: '.*'|bps: 0|g" \
      -e "s|roe: '.*'|roe: 0|g" \
      -e "s|er: '.*'|er: 0|g" \
      -e "s|market_cap: '.*'|market_cap: 0|g" \
      -e "s|payout_ratio: '.*'|payout_ratio: 0|g" \
      -e "s|operating_cashflow: '.*'|operating_cashflow: 0|g"
  python ${MANAGE_PATH} dumpdata --format=yaml stock.localizedstock
} > ${BASE_DIR}/db_stock.yaml

echo Create valid_stocks.json to ${BASE_DIR} based on database.
cat <<- _EOF_ | python ${MANAGE_PATH} shell -v 2
import django
import json
from config.define_module import setup_default_setting
from django.core import serializers

setup_default_setting()
django.setup()

# Import Stock model
from stock.models import Stock

# Collect valid stocks
valid_stocks = Stock.objects.filter(skip_task=False)

# Save stock data as yaml format
with open("${BASE_DIR}/valid_stocks.yaml", "w", encoding="utf-8") as fout:
  serializers.serialize(
    "yaml",
    valid_stocks,
    fields=["pk", "code"],
    stream=fout,
    indent=2,
  )

_EOF_
