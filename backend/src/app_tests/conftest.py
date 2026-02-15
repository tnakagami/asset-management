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

@pytest.fixture
def get_form_param_with_csv_fd():
  def inner(encoding, has_header=True, suffix='.csv'):
    # Setup temporary file
    tmp_fp = tempfile.NamedTemporaryFile(mode='r+', encoding=encoding, suffix=suffix)

    with open(tmp_fp.name, encoding=encoding, mode='w') as csv_file:
      if has_header:
        csv_file.writelines(['Code,Purchase date,Price,Count\n'])
      csv_file.writelines([
        '1234,2021/1/2,1200,50\n',
        '0x01,2024-01-2,1001.12,100\n',
        'xy4a,1990-03-02 00:12,1031.0,200\n',
      ])
      csv_file.flush()
    with open(tmp_fp.name, encoding=encoding, mode='r') as fin:
      csv_file = SimpleUploadedFile(fin.name, bytes(fin.read(), encoding=fin.encoding))
      # Create form data
      params = {
        'encoding': encoding,
        'header': has_header,
      }
      files = {
        'csv_file': csv_file,
      }

    return tmp_fp, csv_file, params, files

  return inner

@pytest.fixture
def get_single_csvfile_form_data(get_form_param_with_csv_fd):
  # Setup temporary file
  tmp_fp, json_file, params, files = get_form_param_with_csv_fd('utf-8', True)

  yield params, files

  # Post-process
  json_file.close()
  tmp_fp.close()

@pytest.fixture(params=[
  ('utf-8',  True), ('shift_jis',  True), ('cp932',  True),
  ('utf-8', False), ('shift_jis', False), ('cp932', False),
], ids=[
  'utf8-with-header', 'sjis-with-header', 'cp932-with-header',
  'utf8-without-header', 'sjis-without-header', 'cp932-without-header',
])
def get_csvfile_form_param(request, get_form_param_with_csv_fd):
  # Define encoding
  encoding, has_header = request.param
  # Setup temporary file
  tmp_fp, json_file, params, files = get_form_param_with_csv_fd(encoding, has_header)

  yield params, files

  # Post-process
  json_file.close()
  tmp_fp.close()

@pytest.fixture(params=[
  'invalid-file-length',
  'value-error',
  'type-error',
  'attribute-error',
  'invalid-extensions',
])
def get_err_form_param_with_csvfile(mocker, request):
  encoding = 'utf-8'
  err_msg = ''
  suffix = '.csv'
  configs = {
    'length_checker': {'return_value': True},
    'extractor': {'side_effect': (lambda row: row)},
    'record_checker': {'return_value': None},
  }
  key = request.param

  if key == 'invalid-file-length':
    configs['length_checker'] = {'side_effect': [True, False]}
    err_msg = 'The length in line 2 is invalid.'
  elif key == 'value-error':
    configs['extractor'] = {'side_effect': ValueError('value error')}
    err_msg = 'Raise exception: value error'
  elif key == 'type-error':
    configs['extractor'] = {'side_effect': TypeError('type error')}
    err_msg = 'Raise exception: type error'
  elif key == 'attribute-error':
    configs['extractor'] = {'side_effect': TypeError('attribute error')}
    err_msg = 'Raise exception: attribute error'
  elif key == 'invalid-extensions':
    suffix = '.txt'
    err_msg = 'The extention has to be &quot;.csv&quot;.'
  # Setup temporary file
  tmp_fp = tempfile.NamedTemporaryFile(mode='r+', encoding=encoding, suffix=suffix)

  with open(tmp_fp.name, encoding=encoding, mode='w') as csv_file:
    csv_file.writelines([
      '0x01,2024-01-2,1001.12,100\n',
      '1234,2021/1/2,1200,50\n',
    ])
    csv_file.flush()
  with open(tmp_fp.name, encoding=encoding, mode='r') as fin:
    csv_file = SimpleUploadedFile(fin.name, bytes(fin.read(), encoding=fin.encoding))
    # Create form data
    params = {
      'encoding': encoding,
      'header': False,
    }
    files = {
      'csv_file': csv_file,
    }

  yield params, files, configs, err_msg

  # Post-process
  csv_file.close()
  tmp_fp.close()