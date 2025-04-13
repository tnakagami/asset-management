import os

def get_settings_module():
  exec_type = os.getenv('EXECUTABLE_TYPE', 'release')

  if exec_type == 'release':
    ret = 'config.settings.release'
  else:
    ret = 'config.settings.development'

  return ret