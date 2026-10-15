"""ارسال پیامک با وب‌سرویس REST نسخهٔ ۱ sms.ir (https://api.sms.ir/v1).

* کد تأیید / قالب‌دار: ``POST /send/verify`` با ``templateId`` و ``parameters``
  (از خطوط خدماتی ارسال می‌شود و به شماره‌های «بلاک تبلیغاتی» هم می‌رسد).
* متن آزاد: ``POST /send/bulk`` با ``lineNumber``.
* اعتبار: ``GET /credit``.

احراز هویت با هدر ``X-API-KEY`` است. کلید سندباکس sms.ir با همین آدرس‌ها کار
می‌کند (در سندباکس فقط قالب 123456 با متغیر CODE موجود است).
"""
import logging

from core.http import ExternalServiceError, http_json

logger = logging.getLogger(__name__)

SMS_IR_BASE_URL = 'https://api.sms.ir/v1'
SMS_IR_HOSTS = ('api.sms.ir',)


class SmsError(RuntimeError):
    pass


def normalize_mobile(value):
    """09xxxxxxxxx from common Iranian formats (+98…, 0098…, 98…, 9…, Persian digits); '' if invalid."""
    from core.persian_digits import normalise_iran_phone

    phone = normalise_iran_phone(str(value or ''))
    if phone.startswith('98') and len(phone) == 12:
        phone = '0' + phone[2:]
    if len(phone) == 11 and phone.startswith('09') and phone.isdigit():
        return phone
    return ''


class SmsIrClient:
    def __init__(self, api_key, timeout=10):
        if not api_key:
            raise SmsError('کلید API پیامک تنظیم نشده است.')
        self.api_key = api_key
        self.timeout = timeout

    def _call(self, method, path, payload=None):
        try:
            result = http_json(
                method, SMS_IR_BASE_URL + path, allowed_hosts=SMS_IR_HOSTS,
                json_body=payload, headers={'X-API-KEY': self.api_key}, timeout=self.timeout,
            )
        except ExternalServiceError as exc:
            logger.warning('sms.ir unreachable: %s', exc)
            raise SmsError('ارتباط با سرویس پیامک برقرار نشد.') from exc
        status = result.get('status')
        if not result.ok or status != 1:
            message = result.get('message') or f'خطای {result.status} از سرویس پیامک'
            raise SmsError(str(message))
        return result.get('data')

    def send_verify(self, mobile, template_id, parameters):
        """Send a template ("ارسال سریع") message. ``parameters`` is a dict name→value."""
        mobile = normalize_mobile(mobile)
        if not mobile:
            raise SmsError('شماره موبایل نامعتبر است.')
        return self._call('POST', '/send/verify', {
            'mobile': mobile,
            'templateId': int(template_id),
            'parameters': [{'name': str(name), 'value': str(value)[:25]} for name, value in parameters.items()],
        })

    def send_bulk(self, line_number, text, mobiles):
        numbers = [m for m in (normalize_mobile(x) for x in mobiles) if m]
        if not numbers:
            raise SmsError('هیچ شماره موبایل معتبری برای ارسال وجود ندارد.')
        try:
            line = int(str(line_number).strip())
        except (TypeError, ValueError):
            raise SmsError('شماره خط ارسال نامعتبر است.')
        return self._call('POST', '/send/bulk', {
            'lineNumber': line,
            'messageText': text,
            'mobiles': numbers,
            'sendDateTime': None,
        })

    def credit(self):
        return self._call('GET', '/credit')


def get_client():
    from .models import SmsSettings

    config = SmsSettings.load()
    if not config.is_usable:
        raise SmsError('سرویس پیامک فعال یا پیکربندی نشده است.')
    return config, SmsIrClient(config.api_key)
