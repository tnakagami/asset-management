import os
from .base import *

ALLOWED_HOSTS =  os.getenv('DJANGO_WWW_VHOST').split(',')