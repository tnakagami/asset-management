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
      -e "s|er: '.*'|er: 0|g"
  python ${MANAGE_PATH} dumpdata --format=yaml stock.localizedstock
} > ${BASE_DIR}/db_stock.yaml