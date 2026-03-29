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
# [Note] Output files are db_industry.yaml and db_stock.yaml in /opt/app/stock/fixtures

# Replace created yaml files to original ones.
mv db_industry.yaml industry.yaml
mv db_stock.yaml stock.yaml

popd
```