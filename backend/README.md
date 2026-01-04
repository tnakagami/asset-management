# Setup backend
## Preparations
### Step1: Execute makemigrations and migrate
Migrations are how Django stores changes to your models and Django manages your database schema automatically by using results of migration. To do this, from the command line, run the following command.

```bash
# In the host environment
./wrapper.sh migrate
docker-compose run --rm backend bash

# In the docker environment
python manage.py migrate django_celery_results
python manage.py migrate django_celery_beat
exit # or press Ctrl + D
```

Please remember the two-step guides to making model changes:

1. Change your models (in `models.py`).
1. Run `./wrapper.sh migrate` to create migrations for those changes in your application and to apply those changes to the database.

### Step2: Create superuser
To create superuser account, let's run following command, where `DJANGO_SUPERUSER_NAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD` are environment variables defined by `env_files/backend/.env`.

```bash
# In the host environment
docker-compose run --rm backend bash

# In the docker environment
python manage.py custom_createsuperuser --username ${DJANGO_SUPERUSER_NAME} --email ${DJANGO_SUPERUSER_EMAIL} --password ${DJANGO_SUPERUSER_PASSWORD}
```

### Step3: Load industry and stock data
You can use default industry data in `stock/fixtures/industry.yaml` and stock data in `stock/fixtures/stock.yaml`.

If you want to load these data, then you should run the following command.

```bash
python manage.py loaddata industry.yaml stock.yaml
#
# Please wait for several minutes...
#
```

### Step4: Create multilingual localization messsages
Run the following commands to reflect translation messages.

```bash
#
# If you need to create/update translated file, type the following commands and execute them.
# In the docker environment
django-admin makemessages -l ${DJANGO_LANGUAGE_CODE:-en}
exit # or press Ctrl + D
#
# Edit .po files using your favorite editor (e.g. vim)
#
# In the host environment
docker-compose run --rm backend bash
#

# In the docker environment
django-admin compilemessages
```

Finally, execute the following command to exit the docker environment.

```bash
exit # or press Ctrl + D
```

## Test
### Preparation
In this project, `pytest` and pytest's third packages are used. In particular, `pytest-django` is useful when I develop web applications using the Django framework.

So, I prepare `conftest.py` in the top directory of `app_tests`. The details are shown below.

```python
# app_tests/conftest.py
import pytest

@pytest.fixture(scope='session', autouse=True)
def django_db_setup(django_db_setup):
  pass
```

After that, I will create test scripts for each application. See [this directory](./src/app_tests) for detail.

### Execution
Run the following command to execute pytest in your pc.

```bash
# In the host environment
./wrapper.sh test
```