## About user-tasks
### Purpose
An `user-task` function is implemented to update stock records by using Web API such as `pandas-datareader`, `yfinance`, and so on.

### How to implement user-tasks
#### Arguments
An `user-task` function is called with the following positional arguments.

| Variable name | Type | Detail |
| :---- | :---- | :---- |
| `idx` | int | Loop counter |
| `pk` | int | Primary key of Stock model |
| `code` | str | Code value of Stock model |
| `total` | int | Total records of Stock table |
| `logger` | celery logger | Logger function |

In addition, you should be satisfied with the following constraints when you define an `user-task` function.
1. This function is wrapped by `@bind_user_function` decorator which is defined in `stock/models.py`.
1. The filename is `user_tasks.py`.
1. The above python script should be in `stock` directory.
1. You should define `stock_records_updater` variable to identify your defined function.

#### Example
The example of `user-task` function is shown below.

```python
from stock.models import Stock, bind_user_function

@bind_user_function
def main_task(pk, logger, **kwargs):
  idx = kwargs.get('idx')
  total = kwargs.get('total')
  stock = Stock.objects.get(pk=pk)
  #
  # After executing something process
  #
  updated_value = run_something()
  stock.price = updated_value
  stock.save()

  logger.info('Success')
  out = f'{idx} / {total}'

  return out

# Define function name to call `update_stock_records`
stock_records_updater = 'main_task'
```
