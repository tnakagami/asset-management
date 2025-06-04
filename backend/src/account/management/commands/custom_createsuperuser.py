from django.contrib.auth.management.commands import createsuperuser
from django.core.management import CommandError
from django.db import DEFAULT_DB_ALIAS

class Command(createsuperuser.Command):
  help = 'Create a superuser with a password non-interactively'

  def add_arguments(self, parser):
    super().add_arguments(parser)
    parser.add_argument(
      '--password', dest='password', default=None,
      help='Specifies the password for the superuser.',
    )

  def handle(self, *args, **options):
    options.setdefault('interactive', False)
    username = options.get('username')
    email = options.get('email')
    password = options.get('password')
    database = options.get('database', DEFAULT_DB_ALIAS)

    if not (username and email and password):
      raise CommandError('--username, --email and --password are required options')

    user_data = {
      'username': username,
      'email': email,
      'password': password,
      'screen_name': 'admin',
    }
    exists = self.UserModel._default_manager.db_manager(database).filter(username=username).exists()

    if not exists:
      self.UserModel._default_manager.db_manager(database).create_superuser(**user_data)