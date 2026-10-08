"""Adapters قابل تست برای درگاه‌های پرداخت.

اعتبارنامه‌ها اول از «تنظیمات درگاه‌های پرداخت» در پنل مدیریت خوانده می‌شوند و
در صورت خالی بودن، از متغیرهای محیطی. برای زرین‌پال حالت تست (سندباکس) هم پشتیبانی می‌شود.
"""
import json
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings

from .models import GatewaySettings

ZARINPAL_PRODUCTION = {
    'request': 'https://api.zarinpal.com/pg/v4/payment/request.json',
    'verify': 'https://api.zarinpal.com/pg/v4/payment/verify.json',
    'start': 'https://www.zarinpal.com/pg/StartPay/',
}
ZARINPAL_SANDBOX = {
    'request': 'https://sandbox.zarinpal.com/pg/v4/payment/request.json',
    'verify': 'https://sandbox.zarinpal.com/pg/v4/payment/verify.json',
    'start': 'https://sandbox.zarinpal.com/pg/StartPay/',
}


def post_json(url, payload, headers=None):
    """POST only to an explicitly allowed HTTPS payment API host."""
    parsed = urlsplit(url)
    allowed_hosts = set(getattr(settings, 'ZARINPAL_ALLOWED_HOSTS', ()))
    if parsed.scheme != 'https' or not parsed.hostname or parsed.hostname not in allowed_hosts:
        raise ValueError('آدرس API درگاه پرداخت مجاز نیست.')

    request = Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', **(headers or {})})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode())


def zarinpal_config():
    """خواندن تنظیمات زرین‌پال (دیتابیس ← متغیر محیطی)."""
    gs = GatewaySettings.objects.filter(key='zarinpal').first()
    merchant_id = ''
    sandbox = False
    if gs:
        merchant_id = gs.effective_credentials()['merchant_id']
        sandbox = gs.is_sandbox
    else:
        merchant_id = getattr(settings, 'ZARINPAL_MERCHANT_ID', '')
    urls = ZARINPAL_SANDBOX if sandbox else ZARINPAL_PRODUCTION
    return merchant_id, urls


def zarinpal_request(transaction, callback_url):
    merchant_id, urls = zarinpal_config()
    if not merchant_id:
        raise RuntimeError('مرچنت کد زرین‌پال تنظیم نشده است. از پنل مدیریت، بخش «تنظیمات درگاه‌های پرداخت» آن را وارد کنید.')
    response = post_json(urls['request'], {
        'merchant_id': merchant_id,
        'amount': transaction.amount * 10,  # زرین‌پال مبلغ را به ریال می‌گیرد
        'description': f'سفارش {transaction.order.order_number} - فروشگاه فایل',
        'callback_url': callback_url,
    })
    data = response.get('data', {}) or {}
    if data.get('code') not in (100, '100'):
        # پیام فارسی خطا در صورت وجود
        errors = response.get('errors') or {}
        message = errors.get('message') or data.get('message') or 'خطا در ایجاد پرداخت زرین‌پال'
        raise RuntimeError(f'زرین‌پال: {message}')
    return data['authority'], f"{urls['start']}{data['authority']}"


def zarinpal_verify(transaction, authority):
    merchant_id, urls = zarinpal_config()
    if not merchant_id:
        raise RuntimeError('مرچنت کد زرین‌پال تنظیم نشده است.')
    response = post_json(urls['verify'], {
        'merchant_id': merchant_id,
        'amount': transaction.amount * 10,  # ریال
        'authority': authority,
    })
    data = response.get('data', {}) or {}
    return data.get('code') in (100, 101, '100', '101'), data
