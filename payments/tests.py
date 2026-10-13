from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings

from cart.models import Cart, CartItem, Order
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
