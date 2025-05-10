from celery import Celery
from celery.schedules import crontab
from .define_module import setup_default_setting
from django.apps import apps

# Set the default Django settings
setup_default_setting()
# Create Celery application
app = Celery('config')
# Setup configure of Celery application
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.beat_schedule = {
  'Cleanup-for-successful-tasks': {
    'task': 'stock.tasks.delete_successful_tasks',
    'schedule': crontab(hour=21, minute=0),
  },
}
# Load task modules from all registered Django apps.
app.autodiscover_tasks(lambda: [config.name for config in apps.get_app_configs()])