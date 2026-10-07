import json
import os
import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.template import Context
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.management.commands.seed_demo import _seed_password
from core.templatetags.seo_tags import _json, product_schema

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

    def test_pwa_worker_has_root_scope_and_offline_fallback_is_public(self):
        worker = self.client.get(reverse('core:service_worker'))
        self.assertEqual(worker.status_code, 200)
        self.assertTrue(worker['Content-Type'].startswith('application/javascript'))
        self.assertEqual(worker['Service-Worker-Allowed'], '/')
        self.assertEqual(worker['Permissions-Policy'], 'camera=(), geolocation=(), microphone=(), payment=(), usb=()')
        self.assertIn(b"url.pathname.startsWith('/downloads/')", worker.content)

        offline = self.client.get(reverse('core:offline'))
        self.assertEqual(offline.status_code, 200)
        self.assertContains(offline, 'اینترنت در دسترس نیست')
        self.assertContains(offline, 'noindex')

        favicon = self.client.get('/favicon.ico')
        self.assertEqual(favicon.status_code, 301)
        self.assertEqual(favicon['Location'], '/static/favicon.ico')

    def test_json_ld_is_script_safe_and_reports_iranian_currency_correctly(self):
        injected_value = '</script><script>alert("xss")</script>'
        serialized = _json({'name': injected_value})
        self.assertNotIn('</script>', serialized)
        self.assertEqual(json.loads(serialized)['name'], injected_value)

        request = RequestFactory().get('/')
        html = str(product_schema(Context({'request': request, 'site_name': 'فایل‌مارکت'}), self.product))
        payload = json.loads(re.search(r'>(.*)</script>', html).group(1))
        self.assertEqual(payload['offers']['priceCurrency'], 'IRR')
        self.assertEqual(payload['offers']['price'], '10000')

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
