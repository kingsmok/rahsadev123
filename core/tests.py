import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.management.commands.seed_demo import _seed_password

from core.models import ContactUs
from product.models import Product, ProductCategory
from services.models import ServiceRequest


class PublicFormAndSafetyTests(TestCase):
    """Regression coverage for public interactions repaired in the UI audit."""

    def setUp(self):
        self.user = User.objects.create_user('seller', password='Safe-pass-123!')
        category = ProductCategory.objects.create(title='فایل تست', slug='test-file')
        self.product = Product.objects.create(
            vendor=self.user,
            title='محصول تست فیلتر',
            slug='test-filter-product',
            description='توضیحات تست',
            price=1000,
            stock_count=1,
        )
        self.product.category.add(category)

    def test_contact_form_rejects_invalid_phone_and_accepts_normalized_phone(self):
        invalid = self.client.post(reverse('core:contact'), {
            'first_name': 'ت', 'last_name': 'کاربر', 'phone': 'bad', 'message': 'کوتاه',
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(ContactUs.objects.count(), 0)

        valid = self.client.post(reverse('core:contact'), {
            'first_name': 'کاربر', 'last_name': 'تست', 'phone': '+989121234567',
            'message': 'این یک پیام آزمایشی معتبر است.',
        })
        self.assertRedirects(valid, reverse('core:contact'))
        self.assertEqual(ContactUs.objects.get().phone, '09121234567')

        persian_digits = self.client.post(reverse('core:contact'), {
            'first_name': 'کاربر', 'last_name': 'فارسی', 'phone': '۰۹۱۲۱۲۳۴۵۶۷',
            'message': 'این پیام با شماره فارسی معتبر است.',
        })
        self.assertRedirects(persian_digits, reverse('core:contact'))
        self.assertEqual(ContactUs.objects.order_by('-id').first().phone, '09121234567')

    def test_registration_requires_terms_acceptance(self):
        payload = {
            'first_name': 'کاربر', 'last_name': 'جدید', 'username': 'new-user',
            'email': 'new-user@example.test', 'password': 'Safe-pass-987!',
        }
        rejected = self.client.post(reverse('account:register'), payload)
        self.assertEqual(rejected.status_code, 200)
        self.assertFalse(User.objects.filter(username='new-user').exists())

        payload['agree'] = 'on'
        accepted = self.client.post(reverse('account:register'), payload)
        self.assertRedirects(accepted, reverse('account:login'))
        self.assertTrue(User.objects.filter(username='new-user').exists())

    def test_invalid_product_filters_do_not_cause_server_errors(self):
        response = self.client.get(reverse('product:product_list'), {
            'min_price': 'not-a-number', 'max_price': '-20', 'brand': 'invalid', 'type': 'unknown',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)

    def test_state_changing_endpoints_require_post_and_profile_isolation(self):
        self.assertTrue(self.client.login(username='seller', password='Safe-pass-123!'))
        self.assertEqual(self.client.get(reverse('account:logout')).status_code, 405)
        self.assertEqual(self.client.get(reverse('cart:add_to_cart', args=[self.product.id])).status_code, 405)

        other = User.objects.create_user('other-user', password='Other-pass-123!')
        response = self.client.get(reverse('dashboard:edit_profile', args=[other.username]))
        self.assertRedirects(response, reverse('dashboard:user_profile'))
        self.assertEqual(other.profile.first_name, '')

    def test_service_request_has_server_side_validation(self):
        invalid = self.client.post(reverse('services:request_service'), {
            'full_name': 'الف', 'phone': 'bad', 'message': 'کم',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(ServiceRequest.objects.count(), 0)

        valid = self.client.post(reverse('services:request_service'), {
            'full_name': 'کاربر آزمایشی', 'phone': '۰۹۱۲۱۲۳۴۵۶۷',
            'email': 'customer@example.test', 'message': 'برای یک سایت فروشگاهی مشاوره لازم دارم.',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(valid.status_code, 200)
        self.assertJSONEqual(valid.content, {'success': True, 'message': 'درخواست شما با موفقیت ثبت شد. کارشناسان ما به‌زودی با شما تماس می‌گیرند.'})
        self.assertEqual(ServiceRequest.objects.get().phone, '09121234567')


class SeedCommandSafetyTests(TestCase):
    @override_settings(DEBUG=False)
    def test_production_seed_requires_non_default_passwords(self):
        with patch.dict(os.environ, {'SEED_ADMIN_PASSWORD': ''}, clear=False):
            with self.assertRaises(CommandError):
                _seed_password('SEED_ADMIN_PASSWORD', 'admin1234')

        with patch.dict(os.environ, {'SEED_ADMIN_PASSWORD': 'A-secure-production-password'}, clear=False):
            self.assertEqual(
                _seed_password('SEED_ADMIN_PASSWORD', 'admin1234'),
                'A-secure-production-password',
            )
