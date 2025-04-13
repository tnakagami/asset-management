## Environment file for Django
Create `.env` file by following the table.

| Name | Detail | Example |
| :--- | :--- | :--- |
| `DJANGO_EXECUTABLE_TYPE` | Definition of executive type (development or release) | development |
| `DJANGO_WWW_VHOST` | Virtual host list | www.example.com,site1.example.com |
| `DJANGO_SECRET_KEY` | Secret key using Django | django-insecure-key |
| `DJANGO_SUPERUSER_NAME` | Username of superuser | superuser |
| `DJANGO_SUPERUSER_EMAIL` | Email of superuser | superuser@local.access |
| `DJANGO_SUPERUSER_PASSWORD` | Password of superuser | superuser-password |

Please see [`env.sample`](./env.sample) for details.