"""کلاینت HTTP کوچک و امن برای سرویس‌های بیرونی (درگاه‌ها، پیامک).

پروژه کتابخانهٔ ``requests`` ندارد؛ این ماژول روی ``urllib`` ساخته شده و:

* فقط به آدرس‌های HTTPS و میزبان‌های مجاز (``allowed_hosts``) درخواست می‌فرستد؛
* پاسخ‌های خطای HTTP (4xx/5xx) را هم به صورت JSON برمی‌گرداند تا پیام خطای
  سرویس قابل خواندن باشد؛
* خطای شبکه را به ``ExternalServiceError`` تبدیل می‌کند.

در تست‌ها ``core.http.urlopen`` جایگزین (mock) می‌شود؛ هیچ تستی به اینترنت
وصل نمی‌شود.
"""
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class ExternalServiceError(RuntimeError):
    """The remote service could not be reached or answered with garbage."""


@dataclass
class HttpResult:
    status: int
    data: object  # parsed JSON (dict/list) or the raw text when not JSON
    text: str

    @property
    def ok(self):
        return 200 <= self.status < 300

    def get(self, key, default=None):
        return self.data.get(key, default) if isinstance(self.data, dict) else default


def check_url(url, allowed_hosts):
    parsed = urlsplit(url)
    hosts = {host.lower() for host in (allowed_hosts or ())}
    if parsed.scheme != 'https' or not parsed.hostname or parsed.hostname.lower() not in hosts:
        raise ValueError('آدرس سرویس بیرونی مجاز نیست.')
    return parsed


def http_json(method, url, *, allowed_hosts, json_body=None, form=None, params=None,
              headers=None, timeout=15):
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urlencode(params)}"
    check_url(url, allowed_hosts)
    request_headers = {'Accept': 'application/json'}
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode('utf-8')
        request_headers['Content-Type'] = 'application/json'
    elif form is not None:
        data = urlencode(form).encode('utf-8')
        request_headers['Content-Type'] = 'application/x-www-form-urlencoded'
    request_headers.update(headers or {})
    request = Request(url, data=data, headers=request_headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, 'status', None) or response.getcode()
            text = response.read().decode('utf-8', errors='replace')
    except HTTPError as exc:
        status = exc.code
        try:
            text = exc.read().decode('utf-8', errors='replace')
        except Exception:  # pragma: no cover - body already consumed
            text = ''
    except (URLError, TimeoutError, OSError) as exc:
        raise ExternalServiceError(str(exc)) from exc
    try:
        payload = json.loads(text) if text else {}
    except ValueError:
        payload = text
    return HttpResult(status=status, data=payload, text=text)
