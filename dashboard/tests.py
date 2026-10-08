from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cart.models import Order
from dashboard.models import Address, Wishlist
from product.models import Product


class AccountDataRegressionTests(TestCase):
    """Coverage for the account forms used by the dashboard interface."""

    def setUp(self):
        self.user = User.objects.create_user('dashboard-user', password='Safe-pass-123!')
        self.address_url = reverse('dashboard:user_addresses')
        self.assertTrue(self.client.login(username='dashboard-user', password='Safe-pass-123!'))

    def address_payload(self, **overrides):
        payload = {
            'title': 'خانه',
            'full_address': 'تهران، خیابان نمونه، پلاک ۱',
            'city': 'تهران',
            'province': 'تهران',
            'postal_code': '1234567890',
            'receiver_name': 'کاربر آزمایشی',
            'phone_number': '09121234567',
        }
        payload.update(overrides)
        return payload

    def test_address_form_normalizes_local_digits_and_preserves_single_default(self):
        first = self.client.post(self.address_url, self.address_payload(is_default='on'))
        self.assertRedirects(first, self.address_url)

        second = self.client.post(self.address_url, self.address_payload(
            title='محل کار',
            postal_code='۱۲۳۴۵۶۷۸۹۰',
            phone_number='۰۹۱۲۱۲۳۴۵۶۷',
            is_default='on',
        ))
        self.assertRedirects(second, self.address_url)

        latest_address = Address.objects.get(title='محل کار')
        self.assertEqual(latest_address.postal_code, '1234567890')
        self.assertEqual(latest_address.phone_number, '09121234567')
        self.assertTrue(latest_address.is_default)
        self.assertEqual(Address.objects.filter(user=self.user, is_default=True).count(), 1)

    def test_invalid_address_keeps_values_and_reopens_the_modal(self):
        response = self.client.post(self.address_url, self.address_payload(postal_code='not-a-code'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_address_modal'])
        self.assertContains(response, 'کد پستی باید فقط شامل اعداد باشد.')
        self.assertContains(response, "window.jQuery('#addressModal').modal('show')", html=False)
        self.assertEqual(Address.objects.count(), 0)

    def test_profile_can_clear_optional_fields_and_normalizes_numeric_input(self):
        profile = self.user.profile
        profile.first_name = 'نام قبلی'
        profile.last_name = 'نام خانوادگی'
        profile.email = 'old@example.test'
        profile.phone = '09121234567'
        profile.card_number = '6037498514785236'
        profile.about_me = 'متن قبلی'
        profile.save()

        edit_url = reverse('dashboard:edit_profile', args=[self.user.username])
        cleared = self.client.post(edit_url, {
            'first_name': '', 'last_name': '', 'email': '', 'phone': '',
            'card_number': '', 'about_me': '',
        })
        self.assertRedirects(cleared, reverse('dashboard:user_profile'))

        profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(profile.first_name, '')
        self.assertEqual(profile.phone, '')
        self.assertEqual(profile.card_number, '')
        self.assertEqual(self.user.email, '')

        normalized = self.client.post(edit_url, {
            'first_name': 'کاربر', 'last_name': 'تست', 'email': 'customer@example.test',
            'phone': '۰۹۱۲۱۲۳۴۵۶۷', 'card_number': '۶۰۳۷۴۹۸۵۱۴۷۸۵۲۳۶', 'about_me': '',
        })
        self.assertRedirects(normalized, reverse('dashboard:user_profile'))
        profile.refresh_from_db()
        self.assertEqual(profile.phone, '09121234567')
        self.assertEqual(profile.card_number, '6037498514785236')
        profile_page = self.client.get(reverse('dashboard:user_profile'))
        self.assertContains(profile_page, '**** **** **** 5236')
        self.assertNotContains(profile_page, '6037498514785236')

    def test_cancellation_request_is_digital_only_and_has_a_non_javascript_fallback(self):
        profile = self.user.profile
        profile.card_number = '6037498514785236'
        profile.save()
        url = reverse('dashboard:orders_return')

        shipped = Order.objects.create(
            user=self.user, total_price=1000, final_price=1000, status='shipped',
        )
        rejected = self.client.post(url, {'order_number': shipped.order_number}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(rejected.status_code, 200)
        self.assertFalse(rejected.json()['success'])
        self.assertIn('پرداخت‌شده', rejected.json()['message'])
        shipped.refresh_from_db()
        self.assertEqual(shipped.status, 'shipped')

        paid = Order.objects.create(
            user=self.user, total_price=1000, final_price=1000, status='paid',
        )
        accepted = self.client.post(url, {'order_number': paid.order_number}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(accepted.json()['success'])
        paid.refresh_from_db()
        self.assertEqual(paid.status, 'processing')

        pending = Order.objects.create(
            user=self.user, total_price=1000, final_price=1000, status='pending',
        )
        fallback = self.client.post(url, {'order_number': pending.order_number})
        self.assertRedirects(fallback, url)
        pending.refresh_from_db()
        self.assertEqual(pending.status, 'processing')

    def test_wishlist_removal_is_post_only_and_returns_ajax_feedback(self):
        product = Product.objects.create(
            vendor=self.user, title='فایل مورد علاقه', slug='favorite-file',
            description='توضیحات آزمایشی', price=1000, stock_count=1,
        )
        Wishlist.objects.create(user=self.user, product=product)
        url = reverse('dashboard:remove_from_wishlist', args=[product.id])

        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertFalse(Wishlist.objects.filter(user=self.user, product=product).exists())
