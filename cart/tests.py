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


class CouponRecalculationTests(TestCase):
    """A coupon must stay consistent with the cart it is applied to."""

    def setUp(self):
        self.user = User.objects.create_user('coupon-audit', password='Safe-pass-123!')
        self.expensive = Product.objects.create(
            vendor=self.user, title='فایل گران', slug='expensive-file',
            description='توضیح', price=600000,
        )
        self.cheap = Product.objects.create(
            vendor=self.user, title='فایل ارزان', slug='cheap-file',
            description='توضیح', price=100000,
        )
        self.coupon = Coupon.objects.create(
            code='AUDIT500', discount_type='fixed', discount_value=500000,
            valid_from=timezone.now(), valid_to=timezone.now() + timedelta(days=1),
            maximum_discount=500000,
        )
        self.cart = Cart.objects.create(user=self.user)

    def _apply(self):
        return self.client.post('/cart/apply_coupon/', {'coupon_code': 'AUDIT500'})

    def test_discount_is_capped_at_the_cart_total_after_an_item_is_removed(self):
        self.client.force_login(self.user)
        CartItem.objects.create(cart=self.cart, product=self.expensive)
        CartItem.objects.create(cart=self.cart, product=self.cheap)

        self._apply()
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.coupon_discount, 500000)
        self.assertEqual(self.cart.final_price, 200000)

        # Removing the item that justified the discount must not leave a
        # 500,000 discount on a 100,000 cart: the order would be free.
        item = CartItem.objects.get(cart=self.cart, product=self.expensive)
        self.client.post(f'/cart/remove/{item.pk}/')
        self.cart.refresh_from_db()

        self.assertLessEqual(self.cart.coupon_discount, self.cart.total_price)
        self.assertEqual(self.cart.final_price, 0)

    def test_coupon_below_minimum_order_amount_is_dropped_when_cart_shrinks(self):
        self.client.force_login(self.user)
        coupon = Coupon.objects.create(
            code='MIN400', discount_type='fixed', discount_value=50000,
            valid_from=timezone.now(), valid_to=timezone.now() + timedelta(days=1),
            minimum_order_amount=400000,
        )
        CartItem.objects.create(cart=self.cart, product=self.expensive)
        CartItem.objects.create(cart=self.cart, product=self.cheap)

        self.client.post('/cart/apply_coupon/', {'coupon_code': 'MIN400'})
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.coupon, coupon)

        item = CartItem.objects.get(cart=self.cart, product=self.expensive)
        self.client.post(f'/cart/remove/{item.pk}/')
        self.cart.refresh_from_db()

        # 100,000 no longer reaches the 400,000 minimum, so the coupon is gone.
        self.assertIsNone(self.cart.coupon)
        self.assertEqual(self.cart.coupon_discount, 0)
        self.assertEqual(self.cart.final_price, 100000)

    def test_cart_view_revalidates_a_stale_discount(self):
        """A discount recorded in another tab is corrected when the cart opens."""
        self.client.force_login(self.user)
        CartItem.objects.create(cart=self.cart, product=self.cheap)
        Cart.objects.filter(pk=self.cart.pk).update(
            coupon=self.coupon, coupon_discount=500000,
        )

        self.client.get('/cart/')
        self.cart.refresh_from_db()

        self.assertLessEqual(self.cart.coupon_discount, self.cart.total_price)
        self.assertEqual(self.cart.coupon_discount, 100000)


class CouponReservationTests(TestCase):
    """A reserved coupon use must be returned when no payment follows."""

    def setUp(self):
        self.user = User.objects.create_user('coupon-reserve', password='Safe-pass-123!')
        self.product = Product.objects.create(
            vendor=self.user, title='فایل رزرو', slug='reserve-file',
            description='توضیح', price=300000,
        )
        self.coupon = Coupon.objects.create(
            code='RESERVE10', discount_type='fixed', discount_value=50000,
            valid_from=timezone.now(), valid_to=timezone.now() + timedelta(days=1),
            max_usage=5,
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product)
        self.client.force_login(self.user)

    def test_removing_a_coupon_returns_its_reserved_use(self):
        self.client.post('/cart/apply_coupon/', {'coupon_code': 'RESERVE10'})
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.usage_count, 1)

        response = self.client.post('/cart/remove_coupon/')
        self.assertEqual(response.status_code, 302)

        self.cart.refresh_from_db()
        self.coupon.refresh_from_db()
        self.assertIsNone(self.cart.coupon)
        self.assertEqual(self.cart.coupon_discount, 0)
        self.assertEqual(self.coupon.usage_count, 0,
                         'بدون پرداخت نباید از ظرفیت کوپن کم شود')

    def test_a_released_coupon_can_be_applied_to_another_code(self):
        other = Coupon.objects.create(
            code='OTHER20', discount_type='fixed', discount_value=20000,
            valid_from=timezone.now(), valid_to=timezone.now() + timedelta(days=1),
        )
        self.client.post('/cart/apply_coupon/', {'coupon_code': 'RESERVE10'})
        # Before this existed, a second code was refused until the cart was emptied.
        response = self.client.post('/cart/apply_coupon/', {'coupon_code': 'OTHER20'})
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.coupon, self.coupon)

        self.client.post('/cart/remove_coupon/')
        self.client.post('/cart/apply_coupon/', {'coupon_code': 'OTHER20'})
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.coupon, other)

    def test_repeated_apply_and_drop_cannot_exhaust_the_coupon_budget(self):
        """Abuse check: burning a campaign's budget without ever paying."""
        for _ in range(5):
            self.client.post('/cart/apply_coupon/', {'coupon_code': 'RESERVE10'})
            self.client.post('/cart/remove_coupon/')

        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.usage_count, 0)
        self.assertTrue(self.coupon.is_active)

    def test_remove_coupon_requires_post(self):
        self.assertEqual(self.client.get('/cart/remove_coupon/').status_code, 405)


class CouponCapacityTests(TestCase):
    """Filling a coupon's capacity with reservations must not cancel those reservations."""

    def setUp(self):
        from django.test import Client

        vendor = User.objects.create_user('capacity-vendor', password='Safe-pass-123!')
        product = Product.objects.create(
            vendor=vendor, title='فایل ظرفیت', slug='capacity-file', description='توضیح', price=300000,
        )
        self.coupon = Coupon.objects.create(
            code='LAST2', discount_type='fixed', discount_value=50000,
            valid_from=timezone.now(), valid_to=timezone.now() + timedelta(days=1), max_usage=2,
        )
        self.buyers = []
        for name in ('first-buyer', 'second-buyer', 'third-buyer'):
            user = User.objects.create_user(name, password='Safe-pass-123!')
            CartItem.objects.create(cart=Cart.objects.create(user=user), product=product)
            client = Client()
            client.force_login(user)
            self.buyers.append((user, client))

    def _apply(self, client):
        return client.post('/cart/apply_coupon/', {'coupon_code': 'LAST2'})

    def test_holders_keep_their_discount_when_the_last_use_is_reserved(self):
        (first, c1), (second, c2), (third, c3) = self.buyers
        self._apply(c1)
        self._apply(c2)  # reserves the final use

        # Used to deactivate the coupon, so the first buyer's next cart view
        # silently dropped a discount whose use had already been counted.
        c1.get('/cart/')
        self.assertEqual(Cart.objects.get(user=first).coupon, self.coupon)
        self.assertEqual(Cart.objects.get(user=first).coupon_discount, 50000)

        # Capacity is still enforced for a third customer.
        self._apply(c3)
        self.assertIsNone(Cart.objects.get(user=third).coupon)
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.usage_count, 2)
        self.assertTrue(self.coupon.is_active)

    def test_a_released_use_can_be_claimed_again(self):
        (first, c1), (second, c2), (third, c3) = self.buyers
        self._apply(c1)
        self._apply(c2)
        c1.post('/cart/remove_coupon/')

        self._apply(c3)

        self.assertEqual(Cart.objects.get(user=third).coupon, self.coupon)
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.usage_count, 2)

    def test_validity_check_has_no_side_effects(self):
        Coupon.objects.filter(pk=self.coupon.pk).update(usage_count=2)
        self.coupon.refresh_from_db()

        self.assertFalse(self.coupon.is_valid())
        self.coupon.refresh_from_db()
        self.assertTrue(self.coupon.is_active)


class StaleCouponTotalsTests(TestCase):
    """The cart and payment pages must show totals computed after revalidation."""

    def setUp(self):
        self.user = User.objects.create_user('stale-totals', password='Safe-pass-123!')
        product = Product.objects.create(
            vendor=self.user, title='فایل مجموع', slug='totals-file', description='توضیح', price=100000,
        )
        self.coupon = Coupon.objects.create(
            code='GONE', discount_type='fixed', discount_value=40000,
            valid_from=timezone.now() - timedelta(days=2), valid_to=timezone.now() + timedelta(days=1),
            usage_count=1,
        )
        self.cart = Cart.objects.create(user=self.user, coupon=self.coupon, coupon_discount=40000)
        CartItem.objects.create(cart=self.cart, product=product)
        self.client.force_login(self.user)

    def _expire(self):
        Coupon.objects.filter(pk=self.coupon.pk).update(valid_to=timezone.now() - timedelta(minutes=1))

    def test_cart_page_shows_the_corrected_payable_amount_on_first_view(self):
        self._expire()

        response = self.client.get('/cart/')

        self.assertEqual(response.context['final_price'], 100000)
        self.cart.refresh_from_db()
        self.assertIsNone(self.cart.coupon)

    def test_payment_page_revalidates_an_expired_coupon(self):
        self._expire()

        response = self.client.get('/cart/shopping_payment/')

        self.assertEqual(response.context['final_price'], 100000)
        self.cart.refresh_from_db()
        self.assertIsNone(self.cart.coupon)
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.usage_count, 0, 'the dropped reservation is returned')
