# Setup Django
## Preparations
### Step1: Execute makemigrations and migrate
Migrations are how Django stores changes to your models. To do this, from the command line, run the following command, where `app-name` is a Django's application name.

```bash
# In the host environment
docker-compose run --rm django bash

# In the container environment
python manage.py makemigrations app-name
```

By running makemigrations, you're telling Django that you've made some changes to your models and that you'd like the chages to be stored as a migration.

There's a command that will run the migrations for you and manage your database schema automatically - that's called migrate. Now, run migrate to create your model tables in your database.

```bash
# In the docker environment
python manage.py migrate
```

Please remember the three-step guide to making model changes:

1. Change your models (in `models.py`).
1. Run `python manage.py makemigrations app-name` to create migrations for those changes in your application.
1. Run `python manage.py migrate` to apply those changes to the database.

### Step2: Create superuser
To create superuser account, let's run following command, where `DJANGO_SUPERUSER_NAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD` are environment variables defined by `env_files/django/.env`.

```bash
# In the docker environment
python manage.py custom_createsuperuser --username ${DJANGO_SUPERUSER_NAME} --email ${DJANGO_SUPERUSER_EMAIL} --password ${DJANGO_SUPERUSER_PASSWORD}
```

### Step3: Create multilingual localization messsages
Run the following commands to reflect translation messages.

```bash
# 
# If you need to create/update translated file, type the following commands and execute them.
# # In the docker environment
# django-admin makemessages -l your-language # e.g., ja
# exit # or press Ctrl + D
# #
# # Edit .po files using your favorite editor (e.g. vim)
# #
# # In the host environment
# docker-compose run --rm django bash
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