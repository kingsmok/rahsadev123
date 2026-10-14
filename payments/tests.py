from unittest import mock
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from cart.models import Cart, CartItem, Order
from payments import views as payment_views
from payments.gateways import post_json
from payments.models import GatewaySettings, PaymentTransaction
from product.models import Product


@override_settings(ZARINPAL_ALLOWED_HOSTS=('api.zarinpal.com', 'sandbox.zarinpal.com'))
class PaymentGatewayHostValidationTests(SimpleTestCase):
    def test_rejects_non_https_and_unapproved_hosts_before_network_access(self):
        with patch('payments.gateways.urlopen') as urlopen:
            with self.assertRaisesMessage(ValueError, 'مجاز نیست'):
                post_json('http://api.zarinpal.com/pg/v4/payment/request.json', {})
            with self.assertRaisesMessage(ValueError, 'مجاز نیست'):
                post_json('https://example.test/collect', {})
            urlopen.assert_not_called()

    def test_allows_configured_https_gateway_host(self):
        response = MagicMock()
        response.read.return_value = b'{"data": {"code": 100}}'
        with patch('payments.gateways.urlopen') as urlopen:
            urlopen.return_value.__enter__.return_value = response
            data = post_json('https://api.zarinpal.com/pg/v4/payment/request.json', {'amount': 1})

        self.assertEqual(data['data']['code'], 100)
        self.assertEqual(urlopen.call_args.kwargs['timeout'], 15)


class _VerifyingGateway:
    """Minimal gateway adapter that reports a confirmed payment."""

    implemented = True

    def verify(self, transaction, data):
        return True, {'ref_id': 'REF-AUDIT'}


@override_settings(
    LOGIN_RATE_LIMIT_WINDOW_SECONDS=600,
    LOGIN_RATE_LIMIT_IDENTITY_ATTEMPTS=50,
    LOGIN_RATE_LIMIT_IP_ATTEMPTS=100,
)
class PaymentFlowSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('payer', password='Safe-pass-123!')
        self.product = Product.objects.create(
            vendor=self.user, title='فایل پرداختی', slug='paid-file',
            description='توضیح', price=50000,
        )
        GatewaySettings.objects.create(
            key='zarinpal', title='زرین‌پال', is_enabled=True, merchant_id='merchant',
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product)
        self.order = Order.objects.create(
            user=self.user, cart=self.cart, total_price=50000, coupon_discount=0,
            shipping_cost=0, final_price=50000, status='pending',
            items_data={'items': [{'product_id': self.product.pk, 'title': 'فایل پرداختی',
                                   'quantity': 1, 'price': 50000}],
                        'coupon': None, 'discount': 0},
        )
        self.client.force_login(self.user)

    def _start(self):
        return self.client.post(
            f'/payments/start/{self.order.order_number}/', {'gateway': 'zarinpal'},
        )

    def test_a_paid_order_cannot_be_paid_again(self):
        Order.objects.filter(pk=self.order.pk).update(status='paid')

        with patch('payments.gateways.post_json') as post_json:
            response = self._start()
            post_json.assert_not_called()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(PaymentTransaction.objects.count(), 0,
                         'سفارش پرداخت‌شده نباید تراکنش پرداخت جدیدی بسازد')

    def test_a_cancelled_order_cannot_be_paid(self):
        Order.objects.filter(pk=self.order.pk).update(status='cancelled')

        with patch('payments.gateways.post_json') as post_json:
            response = self._start()
            post_json.assert_not_called()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    def test_verified_payment_that_cannot_be_fulfilled_is_recorded_not_500(self):
        """Money already taken must stay reconcilable instead of vanishing."""
        from payments import views as payment_views

        transaction = PaymentTransaction.objects.create(
            order=self.order, gateway='zarinpal', amount=50000,
            authority='AUTH-AUDIT', status='redirected',
        )
        # The vendor removes the product while the customer is on the gateway.
        Product.objects.filter(pk=self.product.pk).delete()

        with patch.dict(payment_views.GATEWAYS, {'zarinpal': _VerifyingGateway()}):
            response = self.client.get(
                '/payments/callback/', {'Authority': 'AUTH-AUDIT', 'Status': 'OK'},
            )

        self.assertEqual(response.status_code, 409)
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, 'failed')
        self.assertTrue(transaction.raw_response.get('unfulfilled'))
        self.assertIn('در دسترس نیست', transaction.raw_response.get('error', ''))
        # The order must not silently become paid for a product that is gone.
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, 'pending')


class CancellationRaceTests(TestCase):
    """A payment the gateway confirms must never be recorded as a plain failure."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.user = User.objects.create_user('racer', password='Safe-pass-123!')
        self.product = Product.objects.create(
            vendor=self.user, title='فایل مسابقه', slug='raced-file',
            description='توضیح', price=80000, stock_count=5, is_unlimited=False,
        )
        GatewaySettings.objects.create(
            key='zarinpal', title='زرین‌پال', is_enabled=True, merchant_id='merchant',
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product)
        self.order = Order.objects.create(
            user=self.user, cart=self.cart, total_price=80000, coupon_discount=0,
            shipping_cost=0, final_price=80000, status='pending',
            items_data={'items': [{'product_id': self.product.pk, 'title': 'فایل مسابقه',
                                   'quantity': 1, 'price': 80000}],
                        'coupon': None, 'discount': 0},
        )
        self.transaction = PaymentTransaction.objects.create(
            order=self.order, gateway='zarinpal', amount=80000,
            authority='AUTH-RACE', status='redirected',
        )
        self.client.force_login(self.user)
        # Cancellation is only accepted once a refund target is on file.
        self.user.profile.card_number = '1234567890123456'
        self.user.profile.save()

    def test_verified_payment_on_a_cancellation_request_is_marked_unfulfilled(self):
        from payments import views as payment_views

        # Tab 1: the customer asks to cancel while the gateway page is open.
        self.client.post('/dashboard/orders_return/',
                         {'order_number': self.order.order_number})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'processing')

        # Tab 2: the gateway confirms and charges the payment.
        with patch.dict(payment_views.GATEWAYS, {'zarinpal': _VerifyingGateway()}):
            response = self.client.get('/payments/callback/',
                                       {'Authority': 'AUTH-RACE', 'Status': 'OK'})

        self.assertEqual(response.status_code, 409)
        self.transaction.refresh_from_db()
        # Labeling this merely "failed" would make staff refund a payment that
        # really did succeed; the unfulfilled marker keeps it reconcilable.
        self.assertTrue(self.transaction.raw_response.get('unfulfilled'))
        self.assertIn('تحویل', self.transaction.raw_response.get('error', ''))

        # Nothing was delivered for money that was taken.
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'processing')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_count, 5)
        self.assertFalse(self.order.download_tokens.exists())


class LimitedStockFulfilmentTests(TestCase):
    """A licence with limited stock must never be oversold."""

    def setUp(self):
        self.vendor = User.objects.create_user('vendor2', password='Safe-pass-123!')
        # Only ONE licence available.
        self.product = Product.objects.create(
            vendor=self.vendor, title='لایسنس محدود', slug='limited-licence',
            description='توضیح', price=100000, stock_count=1, is_unlimited=False,
        )

    def _order_for(self, username):
        user = User.objects.create_user(username, password='Safe-pass-123!')
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, product=self.product)
        return Order.objects.create(
            user=user, cart=cart, total_price=100000, coupon_discount=0,
            shipping_cost=0, final_price=100000, status='pending',
            items_data={'items': [{'product_id': self.product.pk, 'title': 'لایسنس محدود',
                                   'quantity': 1, 'price': 100000}],
                        'coupon': None, 'discount': 0},
        )

    def test_second_buyer_of_the_last_licence_is_not_fulfilled(self):
        from payments import views as payment_views

        order_a = self._order_for('buyer-a')
        order_b = self._order_for('buyer-b')
        tx_a = PaymentTransaction.objects.create(
            order=order_a, gateway='zarinpal', amount=100000, authority='AA',
            status='redirected',
        )
        tx_b = PaymentTransaction.objects.create(
            order=order_b, gateway='zarinpal', amount=100000, authority='BB',
            status='redirected',
        )

        payment_views._complete(tx_a, 'REF-A', {})
        with self.assertRaises(payment_views.FulfilmentError) as caught:
            payment_views._complete(tx_b, 'REF-B', {})

        self.assertIn('موجودی', str(caught.exception))
        self.product.refresh_from_db()

        # Only one buyer may end up with a paid order for the single licence.
        self.assertEqual(Order.objects.filter(status='paid').count(), 1)
        self.assertEqual(self.product.stock_count, 0)
        self.assertEqual(self.product.sales_count, 1)
        # The unfulfilled buyer's transaction stays reconcilable, not "paid".
        tx_b.refresh_from_db()
        self.assertNotEqual(tx_b.status, 'paid')


class GatewayErrorDisclosureTests(TestCase):
    """A gateway failure must be logged, not echoed back to the customer."""

    def setUp(self):
        self.user = User.objects.create_user('payer', password='Safe-pass-123!')
        vendor = User.objects.create_user('gw-vendor', password='Safe-pass-123!')
        self.product = Product.objects.create(
            vendor=vendor, title='فایل درگاه', slug='gateway-file', description='توضیح',
            price=100000, stock_count=5,
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product)
        GatewaySettings.objects.create(
            key='zarinpal', title='زرین‌پال', is_enabled=True, merchant_id='MERCHANT-TEST',
        )
        self.client.force_login(self.user)

    def test_gateway_exception_is_not_shown_to_the_customer(self):
        class ExplodingGateway:
            code = 'zarinpal'
            implemented = True

            def start(self, transaction, callback_url):
                raise RuntimeError(
                    'ConnectionError: HTTPSConnectionPool(host="api.zarinpal.internal") '
                    'merchant_id=SECRET-MERCHANT-12345'
                )

            def verify(self, transaction, data):
                return False, {}

        with mock.patch.dict(payment_views.GATEWAYS, {'zarinpal': ExplodingGateway()}):
            with self.assertLogs('payments.views', level='ERROR') as captured:
                response = self.client.post('/payments/start/new/', {'gateway': 'zarinpal'}, follow=True)

        body = response.content.decode()
        self.assertNotIn('SECRET-MERCHANT-12345', body)
        self.assertNotIn('api.zarinpal.internal', body)
        # ... but support can still find it in the log and on the transaction.
        self.assertIn('SECRET-MERCHANT-12345', '\n'.join(captured.output))
        tx = PaymentTransaction.objects.get(order__user=self.user)
        self.assertEqual(tx.status, 'failed')
        self.assertIn('SECRET-MERCHANT-12345', str(tx.raw_response))

    def test_customer_gets_a_reference_to_quote(self):
        class ExplodingGateway:
            code = 'zarinpal'
            implemented = True

            def start(self, transaction, callback_url):
                raise RuntimeError('boom')

            def verify(self, transaction, data):
                return False, {}

        with mock.patch.dict(payment_views.GATEWAYS, {'zarinpal': ExplodingGateway()}):
            with self.assertLogs('payments.views', level='ERROR'):
                response = self.client.post('/payments/start/new/', {'gateway': 'zarinpal'}, follow=True)

        order = Order.objects.get(user=self.user, status='pending')
        self.assertContains(response, order.order_number)


class GatewayAvailabilityTests(TestCase):
    """درگاهِ پیاده‌سازی‌نشده نباید به مشتری پیشنهاد یا برای شروع پرداخت قبول شود."""

    def setUp(self):
        self.user = User.objects.create_user('gw-user', password='Safe-pass-123!')
        self.product = Product.objects.create(vendor=self.user, title='فایل', slug='gw-file', price=1000)
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product)
        GatewaySettings.objects.create(
            key='snappay', title='اسنپ‌پی', is_enabled=True,
            client_id='cid', client_secret='csecret',
        )
        GatewaySettings.objects.create(
            key='zarinpal', title='زرین‌پال', is_enabled=True, merchant_id='merchant-1',
        )
        self.client.force_login(self.user)

    def test_unimplemented_gateway_is_not_offered(self):
        response = self.client.get(reverse('cart:shopping_payment'))
        offered = [g.key for g in response.context['enabled_gateways']]
        self.assertEqual(offered, ['zarinpal'])

    def test_availability_flags(self):
        snappay = GatewaySettings.objects.get(key='snappay')
        zarinpal = GatewaySettings.objects.get(key='zarinpal')
        self.assertTrue(snappay.is_enabled and snappay.is_configured)
        self.assertFalse(snappay.is_implemented)
        self.assertFalse(snappay.is_available)
        self.assertTrue(zarinpal.is_available)


class CheckoutRedirectCspTests(TestCase):
    """The payment page's CSP must let the browser follow the checkout redirect.

    ``form-action`` governs every hop of a form submission's redirect chain, not
    just the form's own ``action``.  Checkout POSTs to ``payments:start``, which
    answers with a 302 to the gateway; with a bare ``form-action 'self'`` real
    Chrome refused to follow it ("Sending form data to … violates … form-action")
    and no customer could reach the payment page.
    """

    def setUp(self):
        self.user = User.objects.create_user('csp-buyer', password='Safe-pass-123!')
        product = Product.objects.create(
            vendor=self.user, title='فایل CSP', slug='csp-file', description='توضیح', price=40000,
        )
        GatewaySettings.objects.create(key='zarinpal', title='زرین‌پال', is_enabled=True, merchant_id='merchant')
        CartItem.objects.create(cart=Cart.objects.create(user=self.user), product=product)
        self.client.force_login(self.user)

    @staticmethod
    def _form_action(response):
        directives = (part.strip() for part in response['Content-Security-Policy'].split(';'))
        return next(d for d in directives if d.startswith('form-action')).split()[1:]

    def test_gateway_redirect_target_is_allowed_by_the_payment_page_form_action(self):
        from urllib.parse import urlsplit

        form_action = self._form_action(self.client.get(reverse('cart:shopping_payment')))
        self.assertIn("'self'", form_action)
        for index, sandbox in enumerate((False, True)):
            GatewaySettings.objects.filter(key='zarinpal').update(is_sandbox=sandbox)
            gateway_reply = {'data': {'code': 100, 'authority': f'A{index:035d}'}}
            with patch('payments.gateways.post_json', return_value=gateway_reply):
                response = self.client.post(reverse('payments:start', args=['new']), {'gateway': 'zarinpal'})

            self.assertEqual(response.status_code, 302)
            target = urlsplit(response['Location'])
            self.assertIn(f'{target.scheme}://{target.netloc}', form_action, msg=f'sandbox={sandbox}')
