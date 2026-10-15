"""آداپترهای درگاه‌های اقساطی: زرین‌پلاس، اسنپ‌پی و ترب‌پی.

منابع:
* زرین‌پلاس — مستند رسمی https://github.com/zarinplus/docs (payment.md) و افزونهٔ
  رسمی ووکامرس نسخهٔ 3.2: ``POST /payment/v2/request/`` ← هدایت به ``redirect_url``
  ← بازگشت GET به آدرس success با ``authority`` ← ``POST /payment/v2/verify/``
  (کد 200 = اولین تأیید، 201 = قبلاً تأیید شده). مبلغ به ریال.
* اسنپ‌پی (API نسخهٔ 2.x) و ترب‌پی (همان طراحی مسیرها): توکن OAuth با
  ``POST /api/online/v1/oauth/token`` (Basic = client_id:client_secret و
  grant_type=password)، ساخت پرداخت ``POST /api/online/payment/v1/token``، بازگشت
  مشتری با ``state`` و ``transactionId``، سپس ``verify`` و ``settle``؛ در قطعی یا
  خطا وضعیت با ``status`` بازیابی می‌شود. مبالغ به ریال.

آدرس پایهٔ API اسنپ‌پی را خود اسنپ‌پی هنگام قرارداد می‌دهد (و IP سرور و آدرس
بازگشت باید نزد آن‌ها ثبت شود)؛ بنابراین در «تنظیمات درگاه‌های پرداخت» وارد
می‌شود. هیچ‌کدام از این آداپترها در محیط توسعه با حساب واقعی آزموده نشده‌اند؛
تست‌ها پاسخ‌های API را شبیه‌سازی می‌کنند.
"""
import base64
import logging
import secrets
from urllib.parse import urlsplit

from django.core.cache import cache

from core.http import ExternalServiceError, http_json

from .base import PaymentGateway
from .models import GatewaySettings, PaymentTransaction

logger = logging.getLogger('payments')

SNAPPAY_STAGING_BASE_URL = 'https://fms-gateway-staging.apps.public.teh-1.snappcloud.io'
TOROBPAY_DEFAULT_BASE_URL = 'https://cpg.torobpay.com'
ZARINPLUS_API = 'https://api.zarinplus.com'
ZARINPLUS_PAY_PAGE = 'https://pwa.zarinplus.com/authority='


class GatewayError(RuntimeError):
    """A gateway refused or failed a request (message is safe for logs, not customers)."""


def _settings(key):
    gateway_settings = GatewaySettings.objects.filter(key=key).first()
    if gateway_settings is None:
        raise GatewayError(f'تنظیمات درگاه {key} وجود ندارد.')
    return gateway_settings, gateway_settings.effective_credentials()


def _https_host(url):
    parts = urlsplit(url or '')
    if parts.scheme != 'https' or not parts.hostname:
        raise GatewayError('آدرس API درگاه باید با https:// شروع شود.')
    return parts.hostname


def to_rial(toman):
    return int(toman) * 10


def international_mobile(mobile):
    """+989xxxxxxxxx (format required by Snapp Pay)."""
    from notifications.sms import normalize_mobile

    local = normalize_mobile(mobile)
    return f'+98{local[1:]}' if local else ''


def local_mobile(mobile):
    from notifications.sms import normalize_mobile

    return normalize_mobile(mobile)


def new_reference_id():
    """Unique per payment attempt; sent as ``transactionId`` and matched on return."""
    for _ in range(10):
        candidate = str(secrets.randbelow(9 * 10 ** 11) + 10 ** 11)  # 12 digits
        if not PaymentTransaction.objects.filter(reference_id=candidate).exists():
            return candidate
    raise GatewayError('ساخت شناسهٔ یکتای تراکنش انجام نشد.')


def _order_lines(order):
    """[(product_id, title, unit_price_toman, count)] from the immutable order snapshot."""
    lines = []
    snapshot = order.items_data if isinstance(order.items_data, dict) else {}
    for item in snapshot.get('items') or []:
        try:
            lines.append((
                str(item.get('product_id') or item.get('id') or ''),
                str(item.get('title') or 'فایل دیجیتال')[:100],
                int(item.get('unit_price') or item.get('price') or 0),
                int(item.get('quantity') or 1),
            ))
        except (TypeError, ValueError):
            continue
    if not lines and order.cart_id:
        for cart_item in order.cart.items.select_related('product'):
            lines.append((str(cart_item.product_id), cart_item.product.title[:100],
                          int(cart_item.product.price), int(cart_item.quantity)))
    return lines


def _error_text(result):
    data = result.data if isinstance(result.data, dict) else {}
    error = data.get('errorData') or data.get('error') or {}
    if isinstance(error, dict) and error.get('message'):
        return str(error['message'])
    return str(data.get('message') or result.text[:200] or f'HTTP {result.status}')


# --------------------------------------------------------------------------- ZarinPlus

class ZarinplusGateway(PaymentGateway):
    code = 'zarinplus'
    implemented = True
    hosts = ('api.zarinplus.com',)

    def start(self, transaction, callback_url, customer=None):
        gateway_settings, credentials = _settings(self.code)
        token = credentials['merchant_id']
        if not token:
            raise GatewayError('توکن پذیرندهٔ زرین‌پلاس تنظیم نشده است.')
        customer = customer or {}
        payload = {
            'amount': to_rial(transaction.amount),
            'success': callback_url,
            'cancel': f'{callback_url}?status=cancel',
            'item': f'سفارش {transaction.order.order_number}',
            'cellphone': local_mobile(customer.get('mobile', '')),
            'email': customer.get('email', '') or '',
            'token': token,
            'gateway_slug': credentials['service_slug'] or 'zarinplus',
        }
        result = http_json('POST', f'{ZARINPLUS_API}/payment/v2/request/', json_body=payload,
                           allowed_hosts=self.hosts, timeout=20)
        if not (result.ok and result.get('status') is True and result.get('authority')):
            raise GatewayError(f'زرین‌پلاس: {_error_text(result)}')
        authority = str(result.get('authority'))
        redirect_url = result.get('redirect_url') or result.get('redirect_ur') or f'{ZARINPLUS_PAY_PAGE}{authority}'
        _https_host(redirect_url)
        return authority, redirect_url

    def verify(self, transaction, callback_data):
        authority = (callback_data.get('authority') or '').strip()
        if not authority or authority != transaction.authority:
            return False, {'error': 'authority mismatch'}
        if (callback_data.get('status') or '').lower() == 'cancel':
            return False, {'state': 'cancelled'}
        _, credentials = _settings(self.code)
        result = http_json('POST', f'{ZARINPLUS_API}/payment/v2/verify/', json_body={
            'authority': authority,
            'token': credentials['merchant_id'],
            'amount': to_rial(transaction.amount),
        }, allowed_hosts=self.hosts, timeout=30)
        data = result.get('data') if isinstance(result.get('data'), dict) else {}
        code = data.get('code')
        ok = bool(result.ok and result.get('status') is True and code in (200, 201, '200', '201'))
        if ok and data.get('amount') not in (None, '') and int(data['amount']) != to_rial(transaction.amount):
            logger.error('ZarinPlus verified amount %s != expected %s for transaction %s',
                         data.get('amount'), to_rial(transaction.amount), transaction.pk)
            return False, {**data, 'error': 'amount mismatch'}
        return ok, {**data, 'ref_id': str(data.get('reference') or '')}


# --------------------------------------------------------------------------- Snapp Pay / Torob Pay

class _OAuthCreditGateway(PaymentGateway):
    """Shared Snapp Pay / Torob Pay client (same API design)."""

    implemented = True
    payment_method = 'INSTALLMENT'
    oauth_scope = ''
    commission_type = 100
    item_category = 'digital'
    international_mobile_format = True

    def base_url(self, gateway_settings, credentials):
        raise NotImplementedError

    def _client(self):
        gateway_settings, credentials = _settings(self.code)
        base = self.base_url(gateway_settings, credentials).rstrip('/')
        host = _https_host(base)
        return base, (host,), credentials

    def _access_token(self, base, hosts, credentials, timeout=15):
        basic = base64.b64encode(f"{credentials['client_id']}:{credentials['client_secret']}".encode()).decode()
        form = {'grant_type': 'password', 'username': credentials['username'], 'password': credentials['password']}
        if self.oauth_scope:
            form['scope'] = self.oauth_scope
        headers = {'Authorization': f'Basic {basic}'}
        result = http_json('POST', f'{base}/api/online/v1/oauth/token', form=form, headers=headers,
                           allowed_hosts=hosts, timeout=timeout)
        if result.status in (400, 415) and not result.get('access_token'):
            # Some deployments document a JSON body for the same endpoint.
            result = http_json('POST', f'{base}/api/online/v1/oauth/token', json_body=form, headers=headers,
                               allowed_hosts=hosts, timeout=timeout)
        token = result.get('access_token')
        if not (result.ok and token):
            raise GatewayError(f'{self.code}: احراز هویت ناموفق بود ({_error_text(result)})')
        return token

    def _call(self, method, path, *, base, hosts, token, json_body=None, params=None, timeout=30):
        return http_json(method, f'{base}{path}', json_body=json_body, params=params,
                         headers={'Authorization': f'Bearer {token}'}, allowed_hosts=hosts, timeout=timeout)

    @staticmethod
    def _successful(result):
        return bool(result.ok and result.get('successful') is True)

    @staticmethod
    def _response(result):
        data = result.get('response')
        return data if isinstance(data, dict) else {}

    def _mobile(self, customer):
        raw = (customer or {}).get('mobile', '')
        mobile = international_mobile(raw) if self.international_mobile_format else local_mobile(raw)
        if not mobile:
            raise GatewayError('برای پرداخت اقساطی شماره موبایل معتبر لازم است.')
        return mobile

    def build_payload(self, transaction, callback_url, customer):
        order = transaction.order
        lines = _order_lines(order)
        items_total = sum(price * count for _, _, price, count in lines) or (order.total_price or transaction.amount)
        discount = max(0, int(items_total) - int(transaction.amount))
        cart_items = [{
            'id': product_id or str(index),
            'name': title,
            'count': count,
            'amount': to_rial(price),
            'category': self.item_category,
            'commissionType': self.commission_type,
        } for index, (product_id, title, price, count) in enumerate(lines, start=1)]
        if not cart_items:
            cart_items = [{'id': '1', 'name': f'سفارش {order.order_number}', 'count': 1,
                           'amount': to_rial(items_total), 'category': self.item_category,
                           'commissionType': self.commission_type}]
        return {
            'amount': to_rial(items_total),
            'discountAmount': to_rial(discount),
            'externalSourceAmount': 0,
            'mobile': self._mobile(customer),
            'paymentMethodTypeDto': self.payment_method,
            'returnURL': callback_url,
            'transactionId': transaction.reference_id,
            'cartList': [{
                'cartId': str(order.order_number),
                'totalAmount': to_rial(items_total),
                'shippingAmount': 0,
                'taxAmount': 0,
                'isShipmentIncluded': True,
                'isTaxIncluded': True,
                'cartItems': cart_items,
            }],
        }

    def start(self, transaction, callback_url, customer=None):
        base, hosts, credentials = self._client()
        if not transaction.reference_id:
            transaction.reference_id = new_reference_id()
            transaction.save(update_fields=['reference_id', 'updated_at'])
        payload = self.build_payload(transaction, callback_url, customer)
        token = self._access_token(base, hosts, credentials)
        result = self._call('POST', '/api/online/payment/v1/token', base=base, hosts=hosts, token=token,
                            json_body=payload)
        response = self._response(result)
        payment_token = response.get('paymentToken')
        page_url = response.get('paymentPageUrl')
        if not (self._successful(result) and payment_token and page_url):
            raise GatewayError(f'{self.code}: ساخت پرداخت ناموفق بود ({_error_text(result)})')
        _https_host(page_url)
        return str(payment_token), page_url

    def status(self, transaction, *, base, hosts, token):
        result = self._call('GET', '/api/online/payment/v1/status', base=base, hosts=hosts, token=token,
                            params={'paymentToken': transaction.authority}, timeout=20)
        return (self._response(result).get('status') or '').upper() if self._successful(result) else ''

    def verify(self, transaction, callback_data):
        state = (callback_data.get('state') or '').strip().upper()
        if state != 'OK':
            return False, {'state': state or 'MISSING'}
        returned_id = (callback_data.get('transactionId') or '').strip()
        if returned_id and returned_id != transaction.reference_id:
            return False, {'error': 'transactionId mismatch'}

        base, hosts, credentials = self._client()
        token = self._access_token(base, hosts, credentials)
        body = {'paymentToken': transaction.authority}

        try:
            verify_result = self._call('POST', '/api/online/payment/v1/verify', base=base, hosts=hosts,
                                       token=token, json_body=body, timeout=30)
            verified = self._successful(verify_result)
        except ExternalServiceError:
            verify_result, verified = None, False
        if not verified:
            # Recovery: the gateway may have verified the payment even though
            # the reply was lost or reported an error.
            current = self.status(transaction, base=base, hosts=hosts, token=token)
            if current not in ('VERIFY', 'SETTLE'):
                return False, {'step': 'verify', 'status': current,
                               'error': _error_text(verify_result) if verify_result else 'timeout'}
            if current == 'SETTLE':
                return True, {'ref_id': transaction.reference_id, 'status': 'SETTLE', 'recovered': True}

        try:
            settle_result = self._call('POST', '/api/online/payment/v1/settle', base=base, hosts=hosts,
                                       token=token, json_body=body, timeout=30)
            settled = self._successful(settle_result)
        except ExternalServiceError:
            settle_result, settled = None, False
        if not settled:
            current = self.status(transaction, base=base, hosts=hosts, token=token)
            if current != 'SETTLE':
                logger.error('%s payment %s verified but not settled (status=%s)', self.code, transaction.pk, current)
                return False, {'step': 'settle', 'status': current,
                               'error': _error_text(settle_result) if settle_result else 'timeout'}
        response = self._response(settle_result) if settle_result is not None else {}
        return True, {'ref_id': str(response.get('transactionId') or transaction.reference_id), 'status': 'SETTLE'}

    def eligibility(self, amount_toman):
        """(eligible, title, description) — cached briefly; never raises."""
        key = f'payments.eligible.{self.code}.{int(amount_toman)}'
        cached = cache.get(key)
        if cached is not None:
            return cached
        outcome = (True, '', '')
        try:
            base, hosts, credentials = self._client()
            # Short timeouts: this runs while the payment page renders.
            token = self._access_token(base, hosts, credentials, timeout=5)
            result = self._call('GET', '/api/online/offer/v1/eligible', base=base, hosts=hosts, token=token,
                                params={'amount': to_rial(amount_toman)}, timeout=5)
            if self._successful(result):
                response = self._response(result)
                outcome = (bool(response.get('eligible', True)), str(response.get('title_message') or ''),
                           str(response.get('description') or ''))
        except Exception as exc:  # the payment page must render even if the API is down
            logger.warning('%s eligibility check failed: %s', self.code, exc)
        cache.set(key, outcome, 600)
        return outcome


class SnappayGateway(_OAuthCreditGateway):
    code = 'snappay'
    payment_method = 'INSTALLMENT'
    oauth_scope = 'online-merchant'
    commission_type = 100
    item_category = 'digital'
    international_mobile_format = True

    def base_url(self, gateway_settings, credentials):
        base = credentials['api_base_url'] or (SNAPPAY_STAGING_BASE_URL if gateway_settings.is_sandbox else '')
        if not base:
            raise GatewayError('آدرس پایهٔ API اسنپ‌پی تنظیم نشده است.')
        return base


class TorobpayGateway(_OAuthCreditGateway):
    code = 'torobpay'
    payment_method = 'ONLINE_CREDIT'
    oauth_scope = ''
    commission_type = '0'
    item_category = 'other'
    international_mobile_format = False

    def base_url(self, gateway_settings, credentials):
        return credentials['api_base_url'] or TOROBPAY_DEFAULT_BASE_URL
