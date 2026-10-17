"""خرید بدون ثبت‌نام: سبد نشست، پرداخت، دسترسی امن، ساخت حساب اختیاری و پیگیری سفارش.

Gateways and SMS are never reached: ``payments.gateways.post_json`` (Zarinpal)
and ``notifications.sms.http_json`` (sms.ir) are patched.  Products use link
delivery, so downloads need no files on disk.
"""
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from cart.models import Cart, CartItem, Coupon, Order
from core.http import HttpResult
from downloads.models import DownloadToken
from notifications.models import SmsSettings
from payments.models import GatewaySettings, PaymentTransaction
from product.models import DigitalAsset, Product

SMS_OK = HttpResult(200, {'status': 1, 'message': 'موفق', 'data': {'messageId': 7, 'cost': 1.0}}, '')
AUTHORITY = 'A' + '5' * 35
STRONG_PASSWORD = 'Guest-Checkout-2026!'


def _messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


class GuestCheckoutBase(TestCase):
    def setUp(self):
        cache.clear()
        self.vendor = User.objects.create_user('vendor', password='Safe-pass-123!')
        self.product = Product.objects.create(
            vendor=self.vendor, title='قالب فروشگاهی مهمان', slug='guest-theme', description='توضیح',
            price=120000, status='published',
        )
        DigitalAsset.objects.create(product=self.product, source=DigitalAsset.SOURCE_LINK,
                                    external_url='https://dl.example.com/guest-theme.zip')
        GatewaySettings.objects.update_or_create(
            key='zarinpal', defaults={'title': 'زرین‌پال', 'is_enabled': True, 'merchant_id': 'merchant'})

    def add_to_cart(self, client=None, product=None):
        client = client or self.client
        return client.post(reverse('cart:add_to_cart', args=[(product or self.product).pk]), '{}',
                           content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def start(self, data=None, client=None, authority=AUTHORITY):
        client = client or self.client
        payload = {'gateway': 'zarinpal', 'mobile': '09121234567', 'email': 'Buyer@Example.com'}
        payload.update(data or {})
        reply = {'data': {'code': 100, 'authority': authority}}
        with patch('payments.gateways.post_json', return_value=reply) as gateway:
            response = client.post(reverse('payments:start', args=['new']), payload)
        return response, gateway

    def pay(self, client=None, authority=AUTHORITY, code=100):
        client = client or self.client
        with self.captureOnCommitCallbacks(execute=True):
            with patch('payments.gateways.post_json', return_value={'data': {'code': code, 'ref_id': 'REF-G1'}}):
                return client.get(reverse('payments:callback'), {'Authority': authority, 'Status': 'OK'})

    def guest_purchase(self, data=None, client=None):
        client = client or self.client
        self.add_to_cart(client)
        self.start(data, client)
        self.pay(client)
        return Order.objects.get(user__isnull=True, status='paid')

    def configure_sms(self):
        config = SmsSettings.load()
        config.is_enabled = True
        config.api_key = 'SANDBOX-KEY'
        config.otp_login_enabled = True
        config.otp_template_id = 123456
        config.otp_parameter = 'CODE'
        config.save()


class GuestCartTests(GuestCheckoutBase):
    def test_guest_adds_to_cart_and_it_survives_navigation_and_refresh(self):
        response = self.add_to_cart()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['cart_count'], 1)

        page = self.client.get(reverse('cart:cart'))
        self.assertContains(page, 'قالب فروشگاهی مهمان')
        self.assertEqual(self.client.get('/products/').context['cart_count'], 1)
        # Another browser has its own (empty) cart.
        self.assertEqual(Client().get('/products/').context['cart_count'], 0)
        self.assertIsNone(Cart.objects.get().user)

    def test_checkout_is_open_to_guests_and_asks_only_for_mobile_and_optional_email(self):
        self.add_to_cart()
        response = self.client.get(reverse('cart:shopping_payment'))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('name="mobile"', html)
        self.assertIn('autocomplete="tel"', html)
        self.assertIn('name="email"', html)
        self.assertIn('autocomplete="email"', html)
        self.assertIn('name="create_account"', html)
        self.assertNotIn('name="create_account" value="1" form="payment-start-form"\n                                           checked', html)
        self.assertIn(reverse('account:login') + '?next=%2Fcart%2Fshopping_payment%2F', html)
        self.assertIn('data-pay-button', html)
        # No SMS codes configured: an optional account needs a password (hidden until chosen).
        self.assertIn('name="password"', html)
        self.assertIn('autocomplete="new-password"', html)

    def test_with_sms_codes_the_optional_account_needs_no_password(self):
        self.configure_sms()
        self.add_to_cart()
        html = self.client.get(reverse('cart:shopping_payment')).content.decode()
        self.assertNotIn('name="password"', html)
        self.assertIn('کد پیامکی', html)

    def test_guest_can_apply_and_remove_a_coupon(self):
        Coupon.objects.create(code='GUEST10', discount_type='percentage', discount_value=10,
                              valid_to=timezone.now() + timedelta(days=1))
        self.add_to_cart()
        self.client.post(reverse('cart:apply_coupon'), {'coupon_code': 'guest10'})
        cart = Cart.objects.get()
        self.assertEqual((cart.coupon.code, cart.coupon_discount), ('GUEST10', 12000))
        self.client.post(reverse('cart:remove_coupon'))
        cart.refresh_from_db()
        self.assertIsNone(cart.coupon)
        self.assertEqual(Coupon.objects.get().usage_count, 0)

    def test_anonymous_coupon_attempts_are_throttled(self):
        self.add_to_cart()
        for _ in range(10):
            self.client.post(reverse('cart:apply_coupon'), {'coupon_code': 'NOPE'})
        response = self.client.post(reverse('cart:apply_coupon'), {'coupon_code': 'NOPE'}, follow=True)
        self.assertTrue(any('زیاد' in message for message in _messages(response)))

    def test_login_merges_the_guest_cart_into_the_account_cart(self):
        other = Product.objects.create(vendor=self.vendor, title='افزونه', slug='plugin-x', price=50000, status='published')
        user = User.objects.create_user('member', password='Safe-pass-123!')
        account_cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=account_cart, product=other)

        self.add_to_cart()
        self.add_to_cart(product=other)
        response = self.client.post(reverse('account:login') + '?next=/cart/shopping_payment/',
                                    {'username': 'member', 'password': 'Safe-pass-123!'})

        self.assertRedirects(response, '/cart/shopping_payment/', fetch_redirect_response=False)
        self.assertEqual(Cart.objects.count(), 1)
        self.assertEqual(sorted(CartItem.objects.filter(cart__user=user).values_list('product_id', flat=True)),
                         sorted([self.product.pk, other.pk]))

    def test_login_keeps_the_guest_cart_when_the_account_has_none(self):
        User.objects.create_user('member', password='Safe-pass-123!')
        self.add_to_cart()
        self.client.post(reverse('account:login'), {'username': 'member', 'password': 'Safe-pass-123!'})
        self.assertEqual(Cart.objects.get().user.username, 'member')


class GuestPaymentTests(GuestCheckoutBase):
    def test_missing_mobile_is_reported_inline_and_entered_values_are_kept(self):
        self.add_to_cart()
        response, gateway = self.start({'mobile': ''})

        self.assertRedirects(response, reverse('cart:shopping_payment') + '#checkout-details',
                             fetch_redirect_response=False)
        gateway.assert_not_called()
        self.assertFalse(Order.objects.exists())
        page = self.client.get(reverse('cart:shopping_payment')).content.decode()
        error = 'شماره موبایل را وارد کنید؛ رسید'
        self.assertIn(error, page)
        self.assertIn('value="Buyer@Example.com"', page)  # kept exactly as typed
        # The error is shown once; a reload does not repeat it.
        self.assertNotIn(error, self.client.get(reverse('cart:shopping_payment')).content.decode())

    def test_invalid_mobile_or_email_is_rejected(self):
        self.add_to_cart()
        self.start({'mobile': '12345', 'email': 'not-an-email'})
        page = self.client.get(reverse('cart:shopping_payment')).content.decode()
        self.assertIn('شماره موبایل معتبر نیست', page)
        self.assertIn('ایمیل واردشده معتبر نیست', page)
        self.assertFalse(Order.objects.exists())

    def test_guest_order_records_contact_and_a_secret_access_key(self):
        self.add_to_cart()
        response, gateway = self.start({'mobile': '۰۹۱۲ ۱۲۳ ۴۵۶۷'})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].endswith(AUTHORITY))
        order = Order.objects.get()
        self.assertIsNone(order.user)
        self.assertEqual((order.contact_mobile, order.contact_email), ('09121234567', 'buyer@example.com'))
        self.assertGreaterEqual(len(order.access_token), 40)
        self.assertIn(order.pk, self.client.session['guest_orders'])
        tx = PaymentTransaction.objects.get()
        self.assertEqual((tx.status, tx.amount, tx.raw_response['redirect_url']), ('redirected', 120000, response['Location']))

    def test_a_double_submit_reuses_the_payment_already_opened(self):
        self.add_to_cart()
        first, gateway_one = self.start()
        second, gateway_two = self.start()

        gateway_one.assert_called_once()
        gateway_two.assert_not_called()
        self.assertEqual(first['Location'], second['Location'])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(PaymentTransaction.objects.count(), 1)

        # A corrected mobile number opens a fresh payment on the same order.
        third, gateway_three = self.start({'mobile': '09351112233'}, authority='A' + '4' * 35)
        gateway_three.assert_called_once()
        self.assertEqual(Order.objects.get().contact_mobile, '09351112233')
        self.assertEqual(PaymentTransaction.objects.count(), 2)

    def test_typed_details_are_forgotten_once_the_purchase_is_confirmed(self):
        order = self.guest_purchase()
        self.assertIn('checkout_details', self.client.session)
        self.client.get(reverse('payments:successful_done', args=[order.order_number]))
        self.assertNotIn('checkout_details', self.client.session)

    def test_successful_payment_delivers_the_files_in_the_buyers_browser(self):
        self.add_to_cart()
        self.start()
        response = self.pay()

        order = Order.objects.get()
        self.assertRedirects(response, reverse('payments:successful_done', args=[order.order_number]),
                             fetch_redirect_response=False)
        self.assertEqual(order.status, 'paid')
        self.assertFalse(Cart.objects.exists())
        token = DownloadToken.objects.get(order=order)
        self.assertIsNone(token.user)

        page = self.client.get(response['Location'])
        self.assertContains(page, reverse('downloads:download', args=[token.token]))
        self.assertContains(page, reverse('cart:guest_order', args=[order.access_token]))
        download = self.client.get(reverse('downloads:download', args=[token.token]))
        self.assertEqual(download.status_code, 302)
        self.assertEqual(download['Location'], 'https://dl.example.com/guest-theme.zip')

        # Receipt e-mail with the secret link (sent after commit).
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['buyer@example.com'])
        self.assertIn(order.access_token, mail.outbox[0].body)

    def test_another_browser_needs_the_secret_link(self):
        order = self.guest_purchase()
        token = DownloadToken.objects.get(order=order)
        stranger = Client()

        locked = stranger.get(reverse('payments:successful_done', args=[order.order_number]))
        self.assertEqual(locked.status_code, 200)
        self.assertNotContains(locked, token.token)
        self.assertNotContains(locked, order.access_token)
        download = stranger.get(reverse('downloads:download', args=[token.token]))
        self.assertRedirects(download, reverse('cart:track_order'), fetch_redirect_response=False)
        self.assertEqual(DownloadToken.objects.get(pk=token.pk).download_count, 0)
        # The order number alone never unlocks the order for payment either.
        self.assertEqual(stranger.post(reverse('payments:start', args=[order.order_number]),
                                       {'gateway': 'zarinpal'}).status_code, 404)

        # The secret link (shown after payment / e-mailed) unlocks it.
        page = stranger.get(reverse('cart:guest_order', args=[order.access_token]))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page['Referrer-Policy'], 'no-referrer')
        self.assertContains(page, reverse('downloads:download', args=[token.token]))
        self.assertEqual(stranger.get(reverse('downloads:download', args=[token.token])).status_code, 302)

    def test_a_signed_in_stranger_cannot_use_a_guest_download_token(self):
        order = self.guest_purchase()
        token = DownloadToken.objects.get(order=order)
        stranger = Client()
        stranger.force_login(User.objects.create_user('stranger', password='Safe-pass-123!'))
        response = stranger.get(reverse('downloads:download', args=[token.token]))
        self.assertRedirects(response, reverse('cart:track_order'), fetch_redirect_response=False)

    def test_cancelled_payment_returns_to_checkout_with_cart_and_details_kept(self):
        self.add_to_cart()
        self.start({'mobile': '09351112233'})
        response = self.client.get(reverse('payments:callback'), {'Authority': AUTHORITY, 'Status': 'NOK'})

        self.assertRedirects(response, reverse('cart:shopping_payment'), fetch_redirect_response=False)
        self.assertTrue(any('لغو' in message for message in _messages(response)))
        self.assertEqual(PaymentTransaction.objects.get().status, 'failed')
        self.assertEqual(Order.objects.get().status, 'pending')
        page = self.client.get(reverse('cart:shopping_payment')).content.decode()
        self.assertIn('value="09351112233"', page)

        # Retrying reuses the pending order and opens a new payment.
        _, gateway = self.start({'mobile': '09351112233'}, authority='A' + '6' * 35)
        gateway.assert_called_once()
        self.assertEqual(Order.objects.count(), 1)

    def test_failed_verification_offers_a_retry(self):
        self.add_to_cart()
        self.start()
        response = self.pay(code=-51)
        self.assertRedirects(response, reverse('cart:shopping_payment'), fetch_redirect_response=False)
        self.assertEqual(Order.objects.get().status, 'pending')

    def test_a_second_charge_for_a_paid_order_goes_to_the_refund_queue(self):
        order = self.guest_purchase()
        duplicate = PaymentTransaction.objects.create(order=order, gateway='zarinpal', amount=order.final_price,
                                                      authority='A' + '9' * 35, status='redirected')
        response = self.pay(authority=duplicate.authority)

        self.assertEqual(response.status_code, 409)
        self.assertContains(response, 'قبلاً پرداخت شده بود', status_code=409)
        duplicate.refresh_from_db()
        self.assertEqual(duplicate.status, 'failed')
        self.assertTrue(duplicate.raw_response['unfulfilled'] and duplicate.raw_response['duplicate'])
        self.assertIn(duplicate, PaymentTransaction.objects.unfulfilled())
        self.assertEqual(DownloadToken.objects.filter(order=order).count(), 1)

    def test_per_customer_coupon_limit_is_enforced_for_guests_by_contact(self):
        coupon = Coupon.objects.create(code='ONCE', discount_type='fixed', discount_value=20000, per_user_limit=1,
                                       valid_to=timezone.now() + timedelta(days=1))
        Order.objects.create(total_price=1, final_price=1, status='paid', contact_mobile='09121234567',
                             items_data={'items': [], 'coupon': 'ONCE', 'discount': 1})
        self.add_to_cart()
        self.client.post(reverse('cart:apply_coupon'), {'coupon_code': 'ONCE'})
        response, gateway = self.start()

        self.assertRedirects(response, reverse('cart:shopping_payment'), fetch_redirect_response=False)
        gateway.assert_not_called()
        self.assertIsNone(Cart.objects.get().coupon)
        self.assertEqual(Coupon.objects.get(pk=coupon.pk).usage_count, 0)

    def test_a_guest_order_fully_covered_by_a_coupon_needs_no_gateway(self):
        Coupon.objects.create(code='FREE', discount_type='percentage', discount_value=100,
                              valid_to=timezone.now() + timedelta(days=1))
        self.add_to_cart()
        self.client.post(reverse('cart:apply_coupon'), {'coupon_code': 'FREE'})
        with self.captureOnCommitCallbacks(execute=True):
            response, gateway = self.start()

        gateway.assert_not_called()
        order = Order.objects.get()
        self.assertEqual((order.status, order.final_price, order.user), ('paid', 0, None))
        self.assertRedirects(response, reverse('payments:successful_done', args=[order.order_number]),
                             fetch_redirect_response=False)
        self.assertEqual(self.client.get(response['Location']).status_code, 200)


class GuestAccountPasswordModeTests(GuestCheckoutBase):
    """No SMS codes configured: the optional account uses a password chosen at checkout."""

    def test_opt_in_creates_the_account_after_payment_and_signs_the_buyer_in(self):
        order = self.guest_purchase({'create_account': '1', 'password': STRONG_PASSWORD})
        self.assertTrue(order.create_account_requested)
        self.assertNotIn(STRONG_PASSWORD, str(dict(self.client.session)))

        response = self.client.get(reverse('payments:successful_done', args=[order.order_number]))

        self.assertRedirects(response, reverse('payments:successful_done', args=[order.order_number]),
                             fetch_redirect_response=False)
        user = User.objects.get(username='09121234567')
        self.assertEqual(user.email, 'buyer@example.com')
        self.assertTrue(user.check_password(STRONG_PASSWORD))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        order.refresh_from_db()
        self.assertEqual(order.user, user)
        self.assertEqual(DownloadToken.objects.get(order=order).user, user)
        # The unverified mobile is not stored as the SMS-login phone.
        self.assertFalse(Profile.objects.filter(phone='09121234567').exists())
        # The page now renders in account mode, and the guest link sends to login.
        self.assertContains(self.client.get(response['Location']), reverse('dashboard:order_detail', args=[order.order_number]))
        self.assertEqual(Client().get(reverse('cart:guest_order', args=[order.access_token])).status_code, 302)

    def test_without_consent_no_account_is_ever_created(self):
        order = self.guest_purchase()
        page = self.client.get(reverse('payments:successful_done', args=[order.order_number]))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(User.objects.count(), 1)  # only the vendor
        self.assertContains(page, 'id="create-account"')  # the optional invitation

    def test_details_of_an_existing_account_never_touch_that_account(self):
        owner = User.objects.create_user('owner', email='buyer@example.com', password='Owner-pass-123!')
        order = self.guest_purchase({'create_account': '1', 'password': STRONG_PASSWORD})

        page = self.client.get(reverse('payments:successful_done', args=[order.order_number]))

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'ساخت حساب جدید با این اطلاعات ممکن نشد')
        self.assertEqual(User.objects.filter(email__iexact='buyer@example.com').count(), 1)
        owner.refresh_from_db()
        self.assertTrue(owner.check_password('Owner-pass-123!'))
        order.refresh_from_db()
        self.assertIsNone(order.user)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_a_weak_password_is_rejected_before_payment(self):
        self.add_to_cart()
        response, gateway = self.start({'create_account': '1', 'password': '123'})
        gateway.assert_not_called()
        self.assertRedirects(response, reverse('cart:shopping_payment') + '#checkout-details',
                             fetch_redirect_response=False)
        self.assertFalse(Order.objects.exists())
        page = self.client.get(reverse('cart:shopping_payment')).content.decode()
        self.assertIn('data-error-for="password"', page)
        self.assertIn('checked', page)

    def test_invitation_after_purchase_creates_the_account_with_one_field(self):
        order = self.guest_purchase()
        response = self.client.post(reverse('cart:guest_account', args=[order.order_number]),
                                    {'action': 'password', 'password': STRONG_PASSWORD})
        self.assertRedirects(response, reverse('dashboard:order_detail', args=[order.order_number]),
                             fetch_redirect_response=False)
        order.refresh_from_db()
        self.assertEqual(order.user.username, '09121234567')
        self.assertEqual(self.client.get(response['Location']).status_code, 200)

    def test_another_browser_cannot_create_an_account_for_the_order(self):
        order = self.guest_purchase()
        response = Client().post(reverse('cart:guest_account', args=[order.order_number]),
                                 {'action': 'password', 'password': STRONG_PASSWORD})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(User.objects.count(), 1)


class GuestAccountSmsModeTests(GuestCheckoutBase):
    """SMS codes configured: the existing passwordless one-time-code flow verifies the phone."""

    def setUp(self):
        super().setUp()
        self.configure_sms()

    def _confirmation(self, order):
        with patch('notifications.sms.http_json', return_value=SMS_OK) as api:
            page = self.client.get(reverse('payments:successful_done', args=[order.order_number]))
        code = api.call_args.kwargs['json_body']['parameters'][0]['value'] if api.called else None
        return page, code, api

    def test_opted_in_buyer_gets_a_code_and_verifying_creates_the_account(self):
        order = self.guest_purchase({'create_account': '1'})
        page, code, api = self._confirmation(order)

        self.assertEqual(page.status_code, 200)
        self.assertTrue(re.fullmatch(r'\d{5}', code))
        self.assertEqual(api.call_args.kwargs['json_body']['mobile'], '09121234567')
        self.assertContains(page, 'name="code"')
        # Refreshing does not send another SMS.
        self.assertFalse(self._confirmation(order)[2].called)

        response = self.client.post(reverse('cart:guest_account', args=[order.order_number]),
                                    {'action': 'verify', 'code': code})

        self.assertRedirects(response, reverse('dashboard:order_detail', args=[order.order_number]),
                             fetch_redirect_response=False)
        user = User.objects.get(profile__phone='09121234567')
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.email, 'buyer@example.com')
        order.refresh_from_db()
        self.assertEqual(order.user, user)
        self.assertEqual(DownloadToken.objects.get(order=order).user, user)

    def test_verified_phone_of_an_existing_account_adds_the_order_to_it(self):
        member = User.objects.create_user('member', password='Safe-pass-123!')
        member.profile.phone = '09121234567'
        member.profile.save()
        order = self.guest_purchase()
        with patch('notifications.sms.http_json', return_value=SMS_OK) as api:
            self.client.post(reverse('cart:guest_account', args=[order.order_number]), {'action': 'send'})
        code = api.call_args.kwargs['json_body']['parameters'][0]['value']
        self.client.post(reverse('cart:guest_account', args=[order.order_number]), {'action': 'verify', 'code': code})

        order.refresh_from_db()
        self.assertEqual(order.user, member)
        self.assertEqual(User.objects.count(), 2)  # vendor + member, nobody new

    def test_the_answer_to_sending_a_code_does_not_reveal_an_existing_account(self):
        answers = []
        for index, (phone, existing) in enumerate((('09121234567', True), ('09129998877', False))):
            cache.clear()
            authority = 'A' + str(index + 1) * 35
            client = Client()
            if existing:
                member = User.objects.create_user(f'member-{phone}', password='Safe-pass-123!')
                member.profile.phone = phone
                member.profile.save()
            self.add_to_cart(client)
            self.start({'mobile': phone}, client, authority=authority)
            self.pay(client, authority=authority)
            order = Order.objects.get(contact_mobile=phone)
            with patch('notifications.sms.http_json', return_value=SMS_OK):
                response = client.post(reverse('cart:guest_account', args=[order.order_number]), {'action': 'send'})
            answers.append([m.replace(phone[:4], '').replace(phone[-4:], '') for m in _messages(response)])
        self.assertEqual(answers[0], answers[1])

    def test_a_wrong_code_creates_nothing(self):
        order = self.guest_purchase({'create_account': '1'})
        self._confirmation(order)
        self.client.post(reverse('cart:guest_account', args=[order.order_number]), {'action': 'verify', 'code': '00000'})
        order.refresh_from_db()
        self.assertIsNone(order.user)
        self.assertEqual(User.objects.count(), 1)


class LoginAttachesGuestOrdersTests(GuestCheckoutBase):
    def test_signing_in_adds_this_browsers_guest_orders_with_a_matching_contact(self):
        order = self.guest_purchase()
        User.objects.create_user('member', email='buyer@example.com', password='Safe-pass-123!')
        self.client.post(reverse('account:login'), {'username': 'member', 'password': 'Safe-pass-123!'})
        order.refresh_from_db()
        self.assertEqual(order.user.username, 'member')
        self.assertEqual(DownloadToken.objects.get(order=order).user.username, 'member')

    def test_signing_in_with_another_contact_leaves_the_guest_order_alone(self):
        order = self.guest_purchase()
        User.objects.create_user('someone', email='someone@example.com', password='Safe-pass-123!')
        self.client.post(reverse('account:login'), {'username': 'someone', 'password': 'Safe-pass-123!'})
        order.refresh_from_db()
        self.assertIsNone(order.user)


class OrderTrackingTests(GuestCheckoutBase):
    def test_without_sms_the_link_is_emailed_and_unknown_orders_get_the_same_answer(self):
        order = self.guest_purchase()
        mail.outbox.clear()
        url = reverse('cart:track_order')
        with self.captureOnCommitCallbacks(execute=True):
            known = self.client.post(url, {'order_number': order.order_number, 'mobile': '09121234567'})
        with self.captureOnCommitCallbacks(execute=True):
            unknown = Client().post(url, {'order_number': order.order_number, 'mobile': '09120000000'})

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(order.access_token, mail.outbox[0].body)
        self.assertEqual(_messages(known), _messages(unknown))
        self.assertEqual((known.status_code, unknown.status_code), (302, 302))

    def test_with_sms_a_verified_code_opens_the_order(self):
        self.configure_sms()
        order = self.guest_purchase()
        stranger = Client()
        with patch('notifications.sms.http_json', return_value=SMS_OK) as api:
            stranger.post(reverse('cart:track_order'), {'order_number': order.order_number, 'mobile': '09121234567'})
        code = api.call_args.kwargs['json_body']['parameters'][0]['value']
        response = stranger.post(reverse('cart:track_order'), {'action': 'verify', 'code': code})

        self.assertRedirects(response, reverse('cart:guest_order', args=[order.access_token]),
                             fetch_redirect_response=False)
        token = DownloadToken.objects.get(order=order)
        stranger.get(response['Location'])
        self.assertEqual(stranger.get(reverse('downloads:download', args=[token.token])).status_code, 302)

    def test_with_sms_an_unknown_order_sends_nothing_and_fails_like_a_wrong_code(self):
        self.configure_sms()
        with patch('notifications.sms.http_json', return_value=SMS_OK) as api:
            response = self.client.post(reverse('cart:track_order'), {'order_number': '1234567890', 'mobile': '09121234567'})
        api.assert_not_called()
        self.assertTrue(any('اگر سفارشی' in message for message in _messages(response)))
        response = self.client.post(reverse('cart:track_order'), {'action': 'verify', 'code': '12345'})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'کد واردشده درست نیست', status_code=400)

    def test_lookups_are_rate_limited(self):
        url = reverse('cart:track_order')
        for _ in range(5):
            self.client.post(url, {'order_number': '1234567890', 'mobile': '09121234567'})
        self.assertEqual(self.client.post(url, {'order_number': '1234567890', 'mobile': '09121234567'}).status_code, 429)

    def test_unknown_secret_link_is_404(self):
        self.assertEqual(self.client.get(reverse('cart:guest_order', args=['x' * 43])).status_code, 404)


class AccountHolderCheckoutTests(GuestCheckoutBase):
    """Signed-in customers keep the existing flow."""

    def test_signed_in_checkout_has_no_guest_step_and_the_order_belongs_to_the_account(self):
        user = User.objects.create_user('member', email='member@example.com', password='Safe-pass-123!')
        self.client.force_login(user)
        self.add_to_cart()
        html = self.client.get(reverse('cart:shopping_payment')).content.decode()
        self.assertNotIn('name="create_account"', html)
        self.assertNotIn('id="checkout-email"', html)

        response, gateway = self.start({'mobile': '', 'email': ''})
        gateway.assert_called_once()
        order = Order.objects.get()
        self.assertEqual(order.user, user)
        self.assertIsNone(order.access_token)
        self.assertEqual(order.contact_email, 'member@example.com')

        response = self.pay()
        self.assertRedirects(response, reverse('payments:successful_done', args=[order.order_number]),
                             fetch_redirect_response=False)
        page = self.client.get(response['Location'])
        self.assertContains(page, reverse('dashboard:order_detail', args=[order.order_number]))
        self.assertEqual(DownloadToken.objects.get(order=order).user, user)
        self.assertEqual(len(mail.outbox), 0)  # account orders get no guest receipt

    def test_an_account_order_is_still_private_to_its_owner(self):
        user = User.objects.create_user('member', password='Safe-pass-123!')
        self.client.force_login(user)
        self.add_to_cart()
        self.start()
        self.pay()
        order = Order.objects.get()
        anonymous = Client().get(reverse('payments:successful_done', args=[order.order_number]))
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn(reverse('account:login'), anonymous['Location'])
        other = Client()
        other.force_login(User.objects.create_user('other', password='Safe-pass-123!'))
        self.assertEqual(other.get(reverse('payments:successful_done', args=[order.order_number])).status_code, 404)


class GuestOrderStaffTests(GuestCheckoutBase):
    def test_admin_lists_guest_orders_and_shows_the_link_for_support(self):
        order = self.guest_purchase()
        admin = User.objects.create_superuser('boss', 'boss@example.com', 'Safe-pass-123!')
        self.client.force_login(admin)
        listing = self.client.get(reverse('admin:cart_order_changelist') + '?buyer=guest')
        self.assertContains(listing, 'مهمان (09121234567)')
        change = self.client.get(reverse('admin:cart_order_change', args=[order.pk]))
        self.assertContains(change, order.access_token)
        export = self.client.get(reverse('admin_export_orders'))
        self.assertEqual(export.status_code, 200)
        self.assertIn('09121234567', export.content.decode('utf-8'))
        self.assertEqual(self.client.get(reverse('admin_home')).status_code, 200)


class CleanupGuestCartsTests(GuestCheckoutBase):
    def test_abandoned_guest_carts_are_removed_and_their_coupon_use_released(self):
        from django.core.management import call_command

        coupon = Coupon.objects.create(code='LIMITED', discount_type='fixed', discount_value=1000, max_usage=1,
                                       usage_count=1, valid_to=timezone.now() + timedelta(days=30))
        stale = Cart.objects.create(coupon=coupon, coupon_discount=1000)
        CartItem.objects.create(cart=stale, product=self.product)
        old = timezone.now() - timedelta(days=20)
        Cart.objects.filter(pk=stale.pk).update(updated_at=old)
        CartItem.objects.filter(cart=stale).update(created_at=old)
        fresh = Cart.objects.create()
        member_cart = Cart.objects.create(user=self.vendor)
        Cart.objects.filter(pk=member_cart.pk).update(updated_at=old)
        pending = Order.objects.create(cart=stale, total_price=1, final_price=1, status='pending', contact_mobile='09121234567')

        call_command('cleanup_guest_carts', '--days', '14', stdout=open('/dev/null', 'w'))

        self.assertFalse(Cart.objects.filter(pk=stale.pk).exists())
        self.assertTrue(Cart.objects.filter(pk=fresh.pk).exists())
        self.assertTrue(Cart.objects.filter(pk=member_cart.pk).exists())  # account carts are never touched
        self.assertEqual(Coupon.objects.get(pk=coupon.pk).usage_count, 0)
        pending.refresh_from_db()
        self.assertIsNone(pending.cart)  # the order itself is kept
