import pytest
from utils import models

@pytest.mark.utils
@pytest.mark.model
class TestStreaming:
  to_joined_str = lambda _self, xs: ','.join([str(val) for val in xs])
  remove_return_code = lambda _self, val: val.strip()

  def test_echo_buffer(self):
    buffer = models._EchoBuffer()
    val = buffer.write(5)

    assert val == 5

  @pytest.mark.parametrize([
    'has_header',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'with-header',
    'without-header',
  ])
  def test_streaming_csv_file(self, has_header):
    # Define data
    rows = [
      [1, 2],
      [3, 4],
      [7, 9],
    ]
    records = (row for row in rows)
    # Set header if needed
    if has_header:
      header = ['col1', 'col2']
      callback = lambda estimated: self.to_joined_str(header)  == self.remove_return_code(estimated)
    else:
      header = None
      callback = lambda estimated: True
    # Call target function
    item_gen = models.streaming_csv_file(records, header)
    out_bom = next(item_gen)
    out_header = next(item_gen) if has_header else []
    _row0 = next(item_gen)
    _row1 = next(item_gen)
    _row2 = next(item_gen)

    with pytest.raises(StopIteration):
      _ = next(item_gen)

    assert b'\xEF\xBB\xBF' == self.remove_return_code(out_bom)
    assert callback(out_header)
    assert self.to_joined_str(rows[0]) == self.remove_return_code(_row0)
    assert self.to_joined_str(rows[1]) == self.remove_return_code(_row1)
    assert self.to_joined_str(rows[2]) == self.remove_return_code(_row2)