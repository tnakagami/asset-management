## YAML file format
### industry.yaml
The file format is shown below.

```yaml
# For stock.industry model
- model: stock.industry
  pk: Integer
  fields:
    is_defensive: Boolean

# For stock.localizedindustry model
- model: stock.localizedindustry
  pk: Integer
  fields:
    language_code: String
    name: String
    industry: Integer [Ref primary key of stock.industry]
```

### stock.yaml
The file format is shown below.

```yaml
# For stock.stock model
- model: stock.stock
  pk: Integer
  fields:
    code: String
    industry: Integer [Ref primary key of stock.industry]
    price: Decimal
    dividend: Decimal
    per: Decimal
    pbr: Decimal
    eps: Decimal
    bps: Decimal
    roe: Decimal
    er: Decimal
    skip_task: Boolean

# For stock.localizedstock model
- model: stock.localizedstock
  pk: Integer
  fields:
    language_code: String
    name: String
    stock: Integer [Ref primary key of stock.stock]
```

## How to use YAML file
Go to the top directory and then, run the following command.

```bash
./wrapper.sh loaddata
```

## How to update YAML file from database
Build and create `BACKEND CONTAINER` and then, enter it to run the command.

The detail is shown below.

```bash
# =======================
# In the host environment
# =======================
# In the top directory
./wrapper.sh start

# Enter the backend container
docker exec -it backend.asset-management bash

# =========================
# In the docker environment
# =========================
# Change working directory
pushd /opt/app/stock/fixtures

# Run the following command
./dump_db.sh
# [Note] Output files are db_industry.yaml, db_stock.yaml, and valid_stocks.yaml in /opt/app/stock/fixtures

# Replace created yaml files to original ones.
mv db_industry.yaml industry.yaml
mv db_stock.yaml stock.yaml

popd
```

## Add new stock data based on Japan Exchange Group, Inc.
1. Save stock list by following format as `stock_list.yaml`.

    ```yaml
    - code: 8303
      industry: 銀行業
      ja: SBI新生銀行
      en: SBI Shinsei Bank, Limited
    - code: 409A
      industry: 食料品
      ja: オリオンビール
      en: Orion Breweries, Ltd.
    ```

1. Create following python code.

    ```python
    import yaml
    import django
    from config.define_module import setup_default_setting

    #
    # Setup
    #
    setup_default_setting()
    django.setup()

    # Import relevant models
    from django.db import transaction
    from django.db.utils import IntegrityError
    from stock.models import LocalizedIndustry, LocalizedStock, Stock

    def bulk_create(target, classname, instances):
      try:
        with transaction.atomic():
          classname.objects.bulk_create(instances)
        print(f"Create {target} (count: {len(instances)})")
      except IntegrityError as ex:
        print(f"IntegrityError: {ex}")

    # ------------
    # main routine
    # ------------
    # Read target file
    with open("stock_list.yaml", "r", encoding="utf-8") as fin:
      data = yaml.safe_load(fin)

    # Create stock instance if its stock does not exist
    all_codes = set(Stock.objects.values_list("code", flat=True))
    new_stocks = []

    for row in data:
      code, industry_name = str(row["code"]).strip(), row["industry"].strip()

      if code not in all_codes:
        try:
          localized_industry = LocalizedIndustry.get(name=industry_name)
          new_stocks += [Stock(code=code, industry=localized_industry.industry)]
        except LocalizedIndustry.DoesNotExist:
          print(f"Error: {industry_name} does not exist(code={code}).")
        except Exception as ex:
          print(f"Error: {ex}")

    if new_stocks:
      bulk_create("stocks", Stock, new_stocks)

    # Create localized stock instance
    new_localized_stocks = []
    for row in data:
      code = str(row["code"]).strip()
      languages = [(key, val.strip()) for key, val in row.items() if key not in ["code", "industry"]]
      stock = Stock.objects.get(code=code)
      new_localized_stocks += [LocalizedStock(language_code=lang_code, name=name, stock=stock) for (lang_code, name) in languages]

    if new_localized_stocks:
      bulk_create("localized stocks", LocalizedStock, new_localized_stocks)
    ```

3. Run the following command.

    ```bash
    python $(find /opt/app -name "manage.py") shell < above_script_file.py
    ```