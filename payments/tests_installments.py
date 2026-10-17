"""درگاه‌های اقساطی (زرین‌پلاس، اسنپ‌پی، ترب‌پی) با پاسخ‌های شبیه‌سازی‌شدهٔ API.

هیچ‌کدام از این تست‌ها به اینترنت وصل نمی‌شوند: ``payments.installments.http_json``
جایگزین می‌شود و درخواست‌های ارسالی (آدرس، بدنه، هدرها) بررسی می‌شوند.
"""
import base64
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from cart.models import Cart, CartItem, Order
from core.http import ExternalServiceError, HttpResult
from downloads.models import DownloadToken
from payments.gateways import CHECKOUT_REDIRECT_ORIGINS
from payments.models import GatewaySettings, PaymentTransaction
from product.models import DigitalAsset, Product


def ok(data, status=200):
    return HttpResult(status, data, '')


class _InstallmentBase(TestCase):
    gateway = ''

    def setUp(self):
        self.user = User.objects.create_user('bnpl-buyer', password='Safe-pass-123!', email='buyer@example.test')
        self.user.profile.phone = '09121234567'
        self.user.profile.save()
        self.product = Product.objects.create(
            vendor=self.user, title='قالب فروشگاهی', slug='bnpl-theme', description='توضیح',
            price=200000, old_price=250000,
        )
        DigitalAsset.objects.create(product=self.product, file='digital-products/bnpl.zip')
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product)
        self.client.force_login(self.user)

    def start(self, replies, data=None):
        payload = {'gateway': self.gateway}
        payload.update(data or {})
        with patch('payments.installments.http_json', side_effect=replies) as api:
            response = self.client.post(reverse('payments:start', args=['new']), payload)
        return response, api


class ZarinplusTests(_InstallmentBase):
    gateway = 'zarinplus'

    def setUp(self):
        super().setUp()
        GatewaySettings.objects.update_or_create(key='zarinplus', defaults={
            'title': 'زرین‌پلاس', 'is_enabled': True, 'merchant_id': 'MERCHANT-TOKEN'})

    def test_start_sends_rial_amount_and_redirects_to_the_documented_payment_page(self):
        reply = ok({'status': True, 'authority': 'f72705fe8a9b', 'redirect_url': 'https://pwa.zarinplus.com/authority=f72705fe8a9b'})
        response, api = self.start([reply])

        method, url = api.call_args.args
        body = api.call_args.kwargs['json_body']
        self.assertEqual((method, url), ('POST', 'https://api.zarinplus.com/payment/v2/request/'))
        self.assertEqual(body['amount'], 2000000)  # 200,000 toman in rial
        self.assertEqual(body['token'], 'MERCHANT-TOKEN')
        self.assertEqual(body['gateway_slug'], 'zarinplus')
        self.assertEqual(body['cellphone'], '09121234567')
        self.assertTrue(body['success'].endswith(reverse('payments:gateway_callback', args=['zarinplus'])))
        self.assertTrue(body['cancel'].endswith('?status=cancel'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://pwa.zarinplus.com/authority=f72705fe8a9b')
        self.assertIn('https://pwa.zarinplus.com', CHECKOUT_REDIRECT_ORIGINS)
        tx = PaymentTransaction.objects.get()
        self.assertEqual((tx.gateway, tx.authority, tx.status), ('zarinplus', 'f72705fe8a9b', 'redirected'))

    def _started(self):
        self.start([ok({'status': True, 'authority': 'AUTH-1'})])
        return PaymentTransaction.objects.get()

    def test_verified_payment_completes_the_order(self):
        tx = self._started()
        verify = ok({'status': True, 'data': {'code': 200, 'amount': 2000000, 'reference': 'REF-9'}})
        with patch('payments.installments.http_json', return_value=verify) as api:
            response = self.client.get(reverse('payments:gateway_callback', args=['zarinplus']), {'authority': 'AUTH-1'})
        self.assertEqual(api.call_args.kwargs['json_body'], {'authority': 'AUTH-1', 'token': 'MERCHANT-TOKEN', 'amount': 2000000})
        tx.refresh_from_db()
        order = tx.order
        order.refresh_from_db()
        self.assertEqual((tx.status, tx.ref_id, order.status), ('paid', 'REF-9', 'paid'))
        self.assertRedirects(response, reverse('payments:successful_done', args=[order.order_number]),
                             fetch_redirect_response=False)
        self.assertTrue(DownloadToken.objects.filter(order=order, product=self.product).exists())

    def test_already_verified_code_201_is_accepted_once(self):
        tx = self._started()
        verify = ok({'status': True, 'data': {'code': 201, 'amount': 2000000, 'reference': 'REF-9'}})
        with patch('payments.installments.http_json', return_value=verify):
            self.client.get(reverse('payments:gateway_callback', args=['zarinplus']), {'authority': 'AUTH-1'})
        tx.refresh_from_db()
        self.assertEqual(tx.status, 'paid')
        with patch('payments.installments.http_json') as api:
            self.client.get(reverse('payments:gateway_callback', args=['zarinplus']), {'authority': 'AUTH-1'})
        api.assert_not_called()  # a replayed return URL is not verified again

    def test_amount_mismatch_or_failed_verification_does_not_complete(self):
        tx = self._started()
        verify = ok({'status': True, 'data': {'code': 200, 'amount': 10, 'reference': 'X'}})
        with patch('payments.installments.http_json', return_value=verify):
            response = self.client.get(reverse('payments:gateway_callback', args=['zarinplus']), {'authority': 'AUTH-1'})
        tx.refresh_from_db()
        self.assertEqual(tx.status, 'failed')
        self.assertEqual(tx.order.status, 'pending')
        self.assertRedirects(response, reverse('cart:shopping_payment'), fetch_redirect_response=False)

    def test_cancel_return_without_authority_goes_back_to_payment_page(self):
        response = self.client.get(reverse('payments:gateway_callback', args=['zarinplus']), {'status': 'cancel'})
        self.assertRedirects(response, reverse('cart:shopping_payment'), fetch_redirect_response=False)

    def test_unknown_authority_is_404_and_unknown_gateway_is_404(self):
        response = self.client.get(reverse('payments:gateway_callback', args=['zarinplus']), {'authority': 'nope'})
        self.assertEqual(response.status_code, 404)
        response = self.client.get('/payments/callback/paypal/', {'authority': 'x'})
        self.assertEqual(response.status_code, 404)


class SnappayTests(_InstallmentBase):
    gateway = 'snappay'

    def setUp(self):
        super().setUp()
        GatewaySettings.objects.update_or_create(key='snappay', defaults={
            'title': 'اسنپ‌پی', 'is_enabled': True, 'client_id': 'CID', 'client_secret': 'SECRET',
            'username': 'api-user', 'password': 'api-pass', 'api_base_url': 'https://snappay.example.test'})

    def _token(self):
        return ok({'access_token': 'JWT', 'token_type': 'Bearer'})

    def _payment_token(self, url='https://pay.snapp.example/checkout/abc'):
        return ok({'successful': True, 'response': {'paymentToken': 'PAY-TOKEN', 'paymentPageUrl': url}})

    def test_start_authenticates_and_sends_a_consistent_cart(self):
        response, api = self.start([self._token(), self._payment_token()])

        oauth = api.call_args_list[0]
        self.assertEqual(oauth.args, ('POST', 'https://snappay.example.test/api/online/v1/oauth/token'))
        self.assertEqual(oauth.kwargs['form'], {'grant_type': 'password', 'username': 'api-user',
                                                'password': 'api-pass', 'scope': 'online-merchant'})
        expected_basic = base64.b64encode(b'CID:SECRET').decode()
        self.assertEqual(oauth.kwargs['headers']['Authorization'], f'Basic {expected_basic}')

        token_call = api.call_args_list[1]
        self.assertEqual(token_call.args, ('POST', 'https://snappay.example.test/api/online/payment/v1/token'))
        self.assertEqual(token_call.kwargs['headers']['Authorization'], 'Bearer JWT')
        body = token_call.kwargs['json_body']
        tx = PaymentTransaction.objects.get()
        self.assertEqual(body['mobile'], '+989121234567')
        self.assertEqual(body['paymentMethodTypeDto'], 'INSTALLMENT')
        self.assertEqual(body['transactionId'], tx.reference_id)
        self.assertTrue(body['returnURL'].endswith('/payments/callback/snappay/'))
        self.assertEqual(body['amount'], 2000000)
        self.assertEqual(body['discountAmount'], 0)
        cart = body['cartList'][0]
        self.assertEqual(cart['totalAmount'], sum(i['amount'] * i['count'] for i in cart['cartItems']))
        self.assertEqual(cart['cartItems'][0]['commissionType'], 100)
        self.assertEqual((tx.authority, tx.status), ('PAY-TOKEN', 'redirected'))
        # The payment-page host is only known at runtime: the browser is sent
        # there with a navigation (interstitial), not a CSP-blocked redirect.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://pay.snapp.example/checkout/abc')

    def test_coupon_discount_is_reported_separately(self):
        from cart.models import Coupon
        from datetime import timedelta
        from django.utils import timezone

        coupon = Coupon.objects.create(code='OFF', discount_type='fixed', discount_value=50000, usage_count=1,
                                       valid_from=timezone.now() - timedelta(days=1),
                                       valid_to=timezone.now() + timedelta(days=1))
        Cart.objects.filter(pk=self.cart.pk).update(coupon=coupon, coupon_discount=50000)
        _, api = self.start([self._token(), self._payment_token()])
        body = api.call_args_list[1].kwargs['json_body']
        self.assertEqual((body['amount'], body['discountAmount']), (2000000, 500000))
        self.assertEqual(PaymentTransaction.objects.get().amount, 150000)

    def test_mobile_is_required_and_a_typed_mobile_is_saved(self):
        self.user.profile.phone = ''
        self.user.profile.save()
        response, api = self.start([])
        self.assertRedirects(response, reverse('cart:shopping_payment'), fetch_redirect_response=False)
        api.assert_not_called()
        self.assertFalse(PaymentTransaction.objects.exists())

        self.start([self._token(), self._payment_token()], {'mobile': '۰۹۱۲۷۶۵۴۳۲۱'})
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.phone, '09127654321')

    def _started(self):
        self.start([self._token(), self._payment_token()])
        return PaymentTransaction.objects.get()

    def _callback(self, tx, replies, state='OK'):
        # A cross-site POST: no session cookie, no CSRF token.
        anonymous = Client(enforce_csrf_checks=True)
        with patch('payments.installments.http_json', side_effect=replies) as api:
            response = anonymous.post(reverse('payments:gateway_callback', args=['snappay']),
                                      {'transactionId': tx.reference_id, 'state': state, 'amount': '2000000'})
        return response, api

    def test_successful_return_verifies_settles_and_fulfils(self):
        tx = self._started()
        verify = ok({'successful': True, 'response': {'transactionId': 'SNAPP-1'}})
        settle = ok({'successful': True, 'response': {'transactionId': 'SNAPP-1'}})
        response, api = self._callback(tx, [self._token(), verify, settle])

        paths = [urlsplit(call.args[1]).path for call in api.call_args_list]
        self.assertEqual(paths, ['/api/online/v1/oauth/token', '/api/online/payment/v1/verify',
                                 '/api/online/payment/v1/settle'])
        self.assertEqual(api.call_args_list[1].kwargs['json_body'], {'paymentToken': 'PAY-TOKEN'})
        tx.refresh_from_db()
        self.assertEqual((tx.status, tx.ref_id), ('paid', 'SNAPP-1'))
        self.assertEqual(tx.order.status, 'paid')
        self.assertRedirects(response, reverse('payments:successful_done', args=[tx.order.order_number]),
                             fetch_redirect_response=False)

        # The gateway may call back again: nothing is verified or created twice.
        response, api = self._callback(tx, [])
        api.assert_not_called()
        self.assertEqual(DownloadToken.objects.filter(order=tx.order).count(), 1)

    def test_failed_state_marks_the_attempt_failed(self):
        tx = self._started()
        response, api = self._callback(tx, [], state='FAILED')
        api.assert_not_called()
        tx.refresh_from_db()
        self.assertEqual(tx.status, 'failed')
        self.assertEqual(tx.order.status, 'pending')

    def test_lost_verify_reply_is_recovered_through_status(self):
        tx = self._started()
        status_verify = ok({'successful': True, 'response': {'status': 'VERIFY'}})
        settle = ok({'successful': True, 'response': {'transactionId': 'SNAPP-2'}})
        response, api = self._callback(tx, [self._token(), ExternalServiceError('timeout'), status_verify, settle])
        tx.refresh_from_db()
        self.assertEqual(tx.status, 'paid')

    def test_settle_failure_is_not_a_successful_purchase(self):
        tx = self._started()
        verify = ok({'successful': True, 'response': {'transactionId': 'SNAPP-3'}})
        settle_error = ok({'successful': False, 'errorData': {'message': 'error'}}, status=500)
        status_verify = ok({'successful': True, 'response': {'status': 'VERIFY'}})
        self._callback(tx, [self._token(), verify, settle_error, status_verify])
        tx.refresh_from_db()
        self.assertEqual(tx.status, 'failed')
        self.assertEqual(tx.order.status, 'pending')

    def test_unknown_transaction_id_is_404(self):
        response = Client().post(reverse('payments:gateway_callback', args=['snappay']),
                                 {'transactionId': '999', 'state': 'OK'})
        self.assertEqual(response.status_code, 404)


class TorobpayTests(_InstallmentBase):
    gateway = 'torobpay'

    def setUp(self):
        super().setUp()
        GatewaySettings.objects.update_or_create(key='torobpay', defaults={
            'title': 'ترب‌پی', 'is_enabled': True, 'client_id': 'TCID', 'client_secret': 'TSECRET',
            'username': 'torob-user', 'password': 'torob-pass'})

    def test_start_uses_default_host_local_mobile_and_online_credit(self):
        token = ok({'access_token': 'TJWT'})
        payment = ok({'successful': True, 'response': {'paymentToken': 'T-TOKEN', 'paymentPageUrl': 'https://cpg.torobpay.com/pay/T-TOKEN'}})
        response, api = self.start([token, payment])
        self.assertEqual(api.call_args_list[0].args[1], 'https://cpg.torobpay.com/api/online/v1/oauth/token')
        self.assertNotIn('scope', api.call_args_list[0].kwargs['form'])
        body = api.call_args_list[1].kwargs['json_body']
        self.assertEqual(body['paymentMethodTypeDto'], 'ONLINE_CREDIT')
        self.assertEqual(body['mobile'], '09121234567')
        self.assertEqual(body['cartList'][0]['cartItems'][0]['commissionType'], '0')
        self.assertContains(response, 'https://cpg.torobpay.com/pay/T-TOKEN')

    def test_token_endpoint_falls_back_to_a_json_body(self):
        rejected = ok({'error': 'unsupported_media_type'}, status=415)
        token = ok({'access_token': 'TJWT'})
        payment = ok({'successful': True, 'response': {'paymentToken': 'T2', 'paymentPageUrl': 'https://cpg.torobpay.com/pay/T2'}})
        _, api = self.start([rejected, token, payment])
        self.assertIn('json_body', api.call_args_list[1].kwargs)
        self.assertEqual(PaymentTransaction.objects.get().authority, 'T2')

    def test_gateway_error_keeps_the_customer_on_the_payment_page(self):
        token = ok({'access_token': 'TJWT'})
        refused = ok({'successful': False, 'errorData': {'message': 'merchant not active'}}, status=400)
        response, _ = self.start([token, refused])
        self.assertRedirects(response, reverse('cart:shopping_payment'), fetch_redirect_response=False)
        self.assertEqual(PaymentTransaction.objects.get().status, 'failed')
        self.assertEqual(Order.objects.get().status, 'pending')


class GatewayAdminSecretTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('gw-admin', 'a@example.test', 'Safe-pass-123!')
        self.client.force_login(self.admin)
        self.row = GatewaySettings.objects.get(key='snappay')
        GatewaySettings.objects.filter(pk=self.row.pk).update(client_secret='STORED-SECRET', password='STORED-PASS')

    def test_secrets_are_never_rendered_and_blank_keeps_them(self):
        url = reverse('admin:payments_gatewaysettings_change', args=[self.row.pk])
        page = self.client.get(url)
        self.assertNotContains(page, 'STORED-SECRET')
        self.assertNotContains(page, 'STORED-PASS')
        self.assertContains(page, '/payments/callback/snappay/')
        response = self.client.post(url, {
            'key': 'snappay', 'title': 'اسنپ‌پی', 'is_enabled': 'on', 'order': 0,
            'merchant_id': '', 'client_id': 'CID', 'client_secret': '', 'username': 'u', 'password': '',
            'api_base_url': 'https://snappay.example.test/', 'service_slug': '', 'description': '',
        })
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['adminform'].form.errors)
        self.row.refresh_from_db()
        self.assertEqual((self.row.client_secret, self.row.password), ('STORED-SECRET', 'STORED-PASS'))
        self.assertEqual(self.row.api_base_url, 'https://snappay.example.test')

    def test_api_base_url_must_be_https(self):
        url = reverse('admin:payments_gatewaysettings_change', args=[self.row.pk])
        response = self.client.post(url, {
            'key': 'snappay', 'title': 'اسنپ‌پی', 'order': 0, 'merchant_id': '', 'client_id': '',
            'client_secret': '', 'username': '', 'password': '', 'api_base_url': 'http://insecure.example',
            'service_slug': '', 'description': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('api_base_url', response.context['adminform'].form.errors)


class GatewayRowMigrationTests(TestCase):
    """Migration 0006 seeds the installment rows but leaves Zarinpal to seed_demo.

    When it also created a disabled Zarinpal row, ``seed_demo``'s
    ``get_or_create(defaults={'is_enabled': True})`` no longer applied on a fresh
    install and the demo checkout had no usable gateway.
    """

    def test_installment_rows_exist_disabled_and_zarinpal_is_left_alone(self):
        rows = {row.key: row for row in GatewaySettings.objects.all()}
        self.assertEqual(set(rows), {'zarinplus', 'snappay', 'torobpay'})
        self.assertFalse(any(row.is_enabled for row in rows.values()))

    def test_seed_style_get_or_create_still_enables_zarinpal(self):
        row, created = GatewaySettings.objects.get_or_create(
            key='zarinpal', defaults={'title': 'زرین‌پال', 'is_enabled': True})
        self.assertTrue(created)
        self.assertTrue(row.is_enabled)
