from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from cart.models import Cart, CartItem, Coupon, Order, OrderItem
from downloads.models import DownloadToken
from payments.models import PaymentTransaction
from payments.views import _complete
from product.models import Product


class CheckoutSnapshotTests(TestCase):
    """Checkout must fulfil the immutable order, not a subsequently changed cart."""

    def setUp(self):
        self.user = User.objects.create_user('checkout-user', password='Safe-pass-123!')
        self.paid_product = Product.objects.create(
            vendor=self.user,
            title='فایل پرداخت‌شده',
            slug='paid-file',
            description='توضیح تست',
            price=1000,
            stock_count=2,
            is_unlimited=False,
        )
        self.later_product = Product.objects.create(
            vendor=self.user,
            title='فایل افزوده‌شده بعدی',
            slug='later-file',
            description='توضیح تست',
            price=2000,
            stock_count=2,
        )

    def test_callback_uses_order_snapshot_and_preserves_later_cart_changes(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.paid_product)
        order = Order.objects.create(
            user=self.user,
            cart=cart,
            total_price=1000,
            coupon_discount=0,
            shipping_cost=0,
            final_price=1000,
            status='pending',
        )

        # The customer changes their cart and the product price changes while
        # they are on the payment provider.  The paid order must stay at 1000.
        CartItem.objects.create(cart=cart, product=self.later_product)
        self.paid_product.price = 9000
        self.paid_product.save(update_fields=['price'])

        transaction = PaymentTransaction.objects.create(
            order=order,
            gateway='zarinpal',
            amount=order.final_price,
            authority='checkout-snapshot-test',
        )
        _complete(transaction, ref_id='REF-SNAPSHOT')
        _complete(transaction, ref_id='REF-SNAPSHOT')  # provider callback retry

        order.refresh_from_db()
        self.paid_product.refresh_from_db()
        self.later_product.refresh_from_db()
        cart.refresh_from_db()

        self.assertEqual(order.status, 'paid')
        self.assertEqual(OrderItem.objects.filter(order=order).count(), 1)
        order_item = OrderItem.objects.get(order=order)
        self.assertEqual(order_item.product, self.paid_product)
        self.assertEqual(order_item.unit_price, 1000)
        self.assertEqual(order_item.total_price, 1000)
        self.assertEqual(self.paid_product.sales_count, 1)
        self.assertEqual(self.paid_product.stock_count, 1)
        self.assertEqual(self.later_product.sales_count, 0)

        # Only the paid product leaves a modified cart; a newly added product
        # remains available for a separate checkout.
        self.assertFalse(cart.items.filter(product=self.paid_product).exists())
        self.assertTrue(cart.items.filter(product=self.later_product).exists())

    def test_payment_callback_requires_a_gateway_authority(self):
        self.client.force_login(self.user)
        response = self.client.get('/payments/callback/?Status=OK')
        self.assertEqual(response.status_code, 400)

    def test_download_token_cannot_be_consumed_beyond_its_limit(self):
        order = Order.objects.create(
            user=self.user,
            total_price=1000,
            coupon_discount=0,
            shipping_cost=0,
            final_price=1000,
            status='paid',
            items_data={
                'items': [{'product_id': self.paid_product.id, 'title': self.paid_product.title, 'quantity': 1, 'price': 1000}],
                'coupon': None,
                'discount': 0,
            },
        )
        token = DownloadToken.objects.create(
            user=self.user,
            product=self.paid_product,
            order=order,
            max_downloads=1,
        )

        self.assertTrue(token.register_download())
        self.assertFalse(token.register_download())
        token.refresh_from_db()
        self.assertEqual(token.download_count, 1)

    def test_cart_item_quantity_is_enforced_as_one_in_the_database(self):
        cart = Cart.objects.create(user=self.user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CartItem.objects.create(cart=cart, product=self.paid_product, quantity=2)

    def test_coupon_endpoint_is_post_only_and_enforces_per_user_limit(self):
        coupon = Coupon.objects.create(
            code='ONEUSE',
            discount_type='fixed',
            discount_value=100,
            valid_from=timezone.now() - timedelta(minutes=1),
            valid_to=timezone.now() + timedelta(days=1),
            per_user_limit=1,
        )
        Order.objects.create(
            user=self.user,
            total_price=1000,
            coupon_discount=100,
            shipping_cost=0,
            final_price=900,
            status='paid',
            items_data={
                'items': [{'product_id': self.paid_product.id, 'title': self.paid_product.title, 'quantity': 1, 'price': 1000}],
                'coupon': coupon.code,
                'discount': 100,
            },
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.paid_product)
        self.client.force_login(self.user)

        self.assertEqual(self.client.get('/cart/apply_coupon/').status_code, 405)
        response = self.client.post('/cart/apply_coupon/', {'coupon_code': 'oneuse'}, follow=True)
        self.assertContains(response, 'سقف استفاده شما از این کد تخفیف تکمیل شده است')
        cart.refresh_from_db()
        self.assertIsNone(cart.coupon)
