from dataclasses import dataclass
from datetime import datetime, timezone
from . import factories

class BaseTestUtils:
  def get_pks(self, xs):
    return [obj.pk for obj in xs]

# Get date based on tuple data (yyyy,mm,dd)
def get_date(ymd, tzinfo=timezone.utc):
  date_with_tz = datetime(*ymd, 1, 2, 3, tzinfo=tzinfo)

  return date_with_tz

@dataclass(frozen=True)
class _HTTP_STATUS_CODE:
  # Informational - 1xx
  HTTP_100_CONTINUE:              int = 100
  HTTP_101_SWITCHING_PROTOCOLS:   int = 101
  HTTP_102_PROCESSING:            int = 102
  HTTP_103_EARLY_HINTS:           int = 103
  # Successful - 2xx
  HTTP_200_OK:                    int = 200
  HTTP_201_CREATED:               int = 201
  HTTP_202_ACCEPTED:              int = 202
  HTTP_204_NO_CONTENT:            int = 204
  HTTP_205_RESET_CONTENT:         int = 205
  HTTP_206_PARTIAL_CONTENT:       int = 206
  HTTP_207_MULTI_STATUS:          int = 207
  HTTP_208_ALREADY_REPORTED:      int = 208
  HTTP_226_IM_USED:               int = 226
  # Redirection - 3xx
  HTTP_300_MULTIPLE_CHOICES:      int = 300
  HTTP_301_MOVED_PERMANENTLY:     int = 301
  HTTP_302_FOUND:                 int = 302
  HTTP_303_SEE_OTHER:             int = 303
  HTTP_304_NOT_MODIFIED:          int = 304
  HTTP_305_USE_PROXY:             int = 305
  HTTP_306_RESERVED:              int = 306
  HTTP_307_TEMPORARY_REDIRECT:    int = 307
  HTTP_308_PERMANENT_REDIRECT:    int = 308
  # Client Error - 4xx
  HTTP_400_BAD_REQUEST:           int = 400
  HTTP_401_UNAUTHORIZED:          int = 401
  HTTP_402_PAYMENT_REQUIRED:      int = 402
  HTTP_403_FORBIDDEN:             int = 403
  HTTP_404_NOT_FOUND:             int = 404
  HTTP_405_METHOD_NOT_ALLOWED:    int = 405
  HTTP_406_NOT_ACCEPTABLE:        int = 406
  HTTP_408_REQUEST_TIMEOUT:       int = 408
  # Server Error - 5xx
  HTTP_500_INTERNAL_SERVER_ERROR: int = 500
  HTTP_501_NOT_IMPLEMENTED:       int = 501
  HTTP_502_BAD_GATEWAY:           int = 502
  HTTP_503_SERVICE_UNAVAILABLE:   int = 503
  HTTP_504_GATEWAY_TIMEOUT:       int = 504

  def __judge_code(self, status_code, target):
    return (status_code // 100) == target

  def is_informational(self, status_code):
    return self.__judge_code(status_code, 1) # 1xx
  def is_success(self, status_code):
    return self.__judge_code(status_code, 2) # 2xx
  def is_redirect(self, status_code):
    return self.__judge_code(status_code, 3) # 3xx
  def is_client_error(self, status_code):
    return self.__judge_code(status_code, 4) # 4xx
  def is_server_error(self, status_code):
    return self.__judge_code(status_code, 5) # 5xx

status = _HTTP_STATUS_CODE()

__all__ = [
  'factories',
  'status',
  'get_date',
  'BaseTestUtils',
]