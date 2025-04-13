import os

def setup_default_setting():
  exec_type = os.getenv('DJANGO_EXECUTABLE_TYPE', 'development')
  setting_filename = 'release' if exec_type == 'release' else 'development'
  os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'config.settings.{setting_filename}')