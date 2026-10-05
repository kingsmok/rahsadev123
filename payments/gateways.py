"""Small, testable gateway adapters. Credentials and endpoints are environment driven."""
import json
from urllib.request import Request, urlopen
from django.conf import settings


def post_json(url, payload, headers=None):
    request = Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', **(headers or {})})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode())


def zarinpal_request(transaction, callback_url):
    if not settings.ZARINPAL_MERCHANT_ID:
        raise RuntimeError('ZARINPAL_MERCHANT_ID تنظیم نشده است.')
    response = post_json(getattr(settings, 'ZARINPAL_REQUEST_URL', 'https://api.zarinpal.com/pg/v4/payment/request.json'), {
        'merchant_id': settings.ZARINPAL_MERCHANT_ID, 'amount': transaction.amount,
        'description': f'سفارش {transaction.order.order_number}', 'callback_url': callback_url,
    })
    data = response.get('data', {})
    if data.get('code') not in (100, '100'):
        raise RuntimeError(data.get('message', 'خطا در ایجاد پرداخت زرین‌پال'))
    return data['authority'], f"{getattr(settings, 'ZARINPAL_START_URL', 'https://www.zarinpal.com/pg/StartPay/')}{data['authority']}"


def zarinpal_verify(transaction, authority):
    response = post_json(getattr(settings, 'ZARINPAL_VERIFY_URL', 'https://api.zarinpal.com/pg/v4/payment/verify.json'), {'merchant_id': settings.ZARINPAL_MERCHANT_ID, 'amount': transaction.amount, 'authority': authority})
    data = response.get('data', {})
    return data.get('code') in (100, 101, '100', '101'), data
