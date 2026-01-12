from django.contrib.auth import get_user_model
import csv

empty_qs = get_user_model().objects.none()

class _EchoBuffer:
  def write(self, value):
    return value

def streaming_csv_file(rows, header=None):
  buffer = _EchoBuffer()
  # Write UTF-8 BOM to open this csv file as UTF-8 format in Excel
  yield buffer.write(b'\xEF\xBB\xBF')
  # Create writer
  writer = csv.writer(buffer, lineterminator='\n')
  # Write each data
  if header is not None:
    yield writer.writerow(header)
  for record in rows:
    yield writer.writerow(record)