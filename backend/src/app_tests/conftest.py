import pytest
import tempfile
from django.core.files.uploadedfile import SimpleUploadedFile

@pytest.fixture(scope='session', autouse=True)
def django_db_setup(django_db_setup):
  pass

@pytest.fixture(autouse=True)
def setup_django(settings):
  settings.TIME_ZONE = 'UTC'
  settings.LANGUAGE_CODE = 'en'

@pytest.fixture
def csrf_exempt_django_app(django_app_factory):
  app = django_app_factory(csrf_checks=False)

  return app

@pytest.fixture
def get_form_param_with_json_fd():
  def inner(encoding, suffix='.json'):
    # Setup temporary file
    tmp_fp = tempfile.NamedTemporaryFile(mode='r+', encoding=encoding, suffix=suffix)

    with open(tmp_fp.name, encoding=encoding, mode='w') as json_file:
      json_file.writelines([
        '{\n',
          '"title": "hoge",\n',
          '"detail": {\n',
            '"cash": {\n',
              '"balance": 123,\n',
              '"registered_date": "2001-11-07T00:00:00+09:00"\n',
            '},\n',
            '"purchased_stocks": [\n',
              '{\n',
                '"stock": {},\n',
                '"price": 960.0,\n',
                '"purchase_date": "2000-12-27T00:00:00+09:00",\n',
                '"count": 100\n',
              '}\n',
            ']\n',
          '},\n',
          '"priority": 99,\n',
          '"start_date": "2019-01-01T00:00:00+09:00",\n',
          '"end_date": "5364-12-30T00:00:00+09:00"\n',
        '}\n',
      ])
      json_file.flush()
    with open(tmp_fp.name, encoding=encoding, mode='r') as fin:
      json_file = SimpleUploadedFile(fin.name, bytes(fin.read(), encoding=fin.encoding))
      # Create form data
      params = {
        'encoding': encoding,
      }
      files = {
        'json_file': json_file,
      }

    return tmp_fp, json_file, params, files

  return inner

@pytest.fixture(params=['utf-8-encoding', 'sjis-encoding', 'cp932-encoding'])
def get_jsonfile_form_param(request, get_form_param_with_json_fd):
  # Define encoding
  if request.param == 'utf-8-encoding':
    encoding = 'utf-8'
  elif request.param == 'sjis-encoding':
    encoding = 'shift_jis'
  elif request.param == 'cp932-encoding':
    encoding = 'cp932'
  # Setup temporary file
  tmp_fp, json_file, params, files = get_form_param_with_json_fd(encoding)

  yield params, files

  # Post-process
  json_file.close()
  tmp_fp.close()

@pytest.fixture(params=['invalid-json-format', 'invalid-extensions'])
def get_err_form_param_with_jsonfile(mocker, request):
  err_msg = ''
  input_data = '{}'
  suffix = '.json'

  if request.param == 'invalid-json-format':
    input_data = '}{'
    err_msg = 'Cannot load json file'
  elif request.param == 'invalid-extensions':
    suffix = '.txt'
    err_msg = 'The extention has to be &quot;.json&quot;.'
  # Setup temporary file
  encoding = 'utf-8'
  tmp_fp = tempfile.NamedTemporaryFile(mode='r+', encoding=encoding, suffix=suffix)

  with open(tmp_fp.name, encoding=encoding, mode='w') as json_file:
    json_file.write(input_data)
    json_file.flush()
  with open(tmp_fp.name, encoding=encoding, mode='r') as fin:
    json_file = SimpleUploadedFile(fin.name, bytes(fin.read(), encoding=fin.encoding))
    # Create form data
    params = {
      'encoding': encoding,
    }
    files = {
      'json_file': json_file,
    }

  yield params, files, err_msg

  # Post-process
  json_file.close()
  tmp_fp.close()