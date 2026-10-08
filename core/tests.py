import json
import os
import re
import sys
import tempfile
from io import BytesIO, StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import CommandError
from django.template import Context
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.image_optimization import optimise_uploaded_image
from core.management.commands.seed_demo import _seed_password
from core.storage import CkeditorImageStorage
from core.templatetags.seo_tags import _json, product_schema, webpage_schema

import manage

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


class ImageAndSeoAutomationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('image-owner', password='Safe-pass-123!')
        self.temp_media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.temp_media.cleanup)

    @staticmethod
    def _image_upload(name='large-photo.jpg', size=(320, 160)):
        buffer = BytesIO()
        Image.new('RGB', size, '#2b7780').save(buffer, format='JPEG', quality=96)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')

    @override_settings(IMAGE_OPTIMIZATION_MAX_DIMENSION=100, IMAGE_OPTIMIZATION_WEBP_QUALITY=80)
    def test_new_image_uploads_are_resized_and_converted_to_webp(self):
        product = Product.objects.create(
            vendor=self.user,
            title='محصول تصویر بهینه',
            slug='optimized-image-product',
            description='توضیح محصول دارای تصویر برای تست بهینه‌سازی خودکار.',
            price=15000,
            image=self._image_upload(),
        )
        self.assertTrue(product.image.name.endswith('.webp'))
        with Image.open(product.image.path) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertLessEqual(max(image.size), 100)

    @override_settings(IMAGE_OPTIMIZATION_MAX_DIMENSION=100, IMAGE_OPTIMIZATION_WEBP_QUALITY=80)
    def test_replacing_an_existing_image_is_optimised_again(self):
        product = Product.objects.create(
            vendor=self.user,
            title='محصول تصویر قابل به‌روزرسانی',
            slug='replace-optimized-image',
            description='توضیح محصول برای آزمایش جایگزینی تصویر.',
            price=15000,
            image=self._image_upload('first-image.jpg', (320, 160)),
        )
        first_name = product.image.name

        product.image = self._image_upload('replacement-image.jpg', (480, 240))
        product.save(update_fields=['image'])
        product.refresh_from_db()

        self.assertTrue(product.image.name.endswith('.webp'))
        self.assertNotEqual(product.image.name, first_name)
        with Image.open(product.image.path) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertLessEqual(max(image.size), 100)

    @override_settings(IMAGE_OPTIMIZATION_MAX_DIMENSION=100, IMAGE_OPTIMIZATION_WEBP_QUALITY=80)
    def test_ckeditor_upload_storage_uses_the_same_webp_pipeline(self):
        storage = CkeditorImageStorage(location=self.temp_media.name, base_url='/media/')
        stored_name = storage.save('article-inline.jpg', self._image_upload(size=(320, 160)))

        self.assertTrue(stored_name.startswith('ckeditor-images/'))
        self.assertTrue(stored_name.endswith('.webp'))
        with Image.open(storage.path(stored_name)) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertLessEqual(max(image.size), 100)

    @override_settings(IMAGE_OPTIMIZATION_MAX_DIMENSION=100)
    def test_optimiser_leaves_animated_gif_untouched(self):
        buffer = BytesIO()
        frame = Image.new('P', (20, 20), 1)
        frame.save(buffer, format='GIF', save_all=True, append_images=[frame.copy()], loop=0)
        upload = SimpleUploadedFile('animated.gif', buffer.getvalue(), content_type='image/gif')
        self.assertIsNone(optimise_uploaded_image(upload))

    def test_empty_seo_fields_are_filled_from_real_content_without_overwriting_editor_input(self):
        product = Product.objects.create(
            vendor=self.user,
            title='محصول سئوی خودکار',
            slug='automatic-seo-product',
            description='<p>توضیح معتبر برای ساخت خودکار متای محصول.</p>',
            price=10000,
        )
        self.assertEqual(product.meta_title, 'محصول سئوی خودکار')
        self.assertEqual(product.meta_description, 'توضیح معتبر برای ساخت خودکار متای محصول.')

        product.meta_title = 'عنوان اختصاصی'
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.meta_title, 'عنوان اختصاصی')

    def test_webpage_schema_uses_clean_canonical_and_skips_noindex_routes(self):
        product = Product.objects.create(
            vendor=self.user,
            title='محصول schema خودکار',
            slug='automatic-schema-product',
            description='توضیح محصول برای schema عمومی.',
            price=12000,
        )
        request = RequestFactory().get('/products/%s/%s/?utm_source=test' % (product.pid, product.slug))
        context = Context({
            'request': request,
            'products': product,
            'site_name': 'فایل‌مارکت',
            'canonical_url': 'https://example.test/products/%s/%s/' % (product.pid, product.slug),
            'meta_robots': 'index, follow',
        })
        html = str(webpage_schema(context))
        payload = json.loads(re.search(r'>(.*)</script>', html).group(1))
        self.assertEqual(payload['@type'], 'ItemPage')
        self.assertEqual(payload['url'], context['canonical_url'])
        self.assertNotIn('utm_source', payload['url'])

        homepage = self.client.get(reverse('core:home'))
        self.assertEqual(homepage.status_code, 200)
        self.assertContains(homepage, '"@type":"WebPage"')

        context['meta_robots'] = 'noindex, follow'
        self.assertEqual(webpage_schema(context), '')


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


class ManagePreflightTests(SimpleTestCase):
    """The startup check must name the missing package, not just crash."""

    def _write_requirements(self, text):
        handle = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8')
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_parse_requirements_skips_noise(self):
        path = self._write_requirements(
            '# a comment\n'
            '\n'
            'Django==5.2.17  # trailing note\n'
            '-r other.txt\n'
            '--index-url https://example.invalid\n'
            'Pillow>=11\n'
            'somepkg[extra]==1.0\n'
        )
        self.assertEqual(
            manage._parse_requirements(path),
            [('Django', '==5.2.17'), ('Pillow', '>=11'), ('somepkg', '[extra]==1.0')],
        )

    def test_missing_requirements_ignores_name_spelling(self):
        path = self._write_requirements('DJANGO==5.2.17\ndjango-ckeditor-5==0.2.20\nnot-a-real-package==9.9.9\n')
        self.assertEqual(manage.missing_requirements(path), [('not-a-real-package', '==9.9.9')])

    def test_missing_requirements_handles_absent_file(self):
        self.assertEqual(manage.missing_requirements(self._write_requirements('') + '.missing'), [])

    def test_shipped_requirements_are_installed(self):
        self.assertEqual(manage.missing_requirements(), [])

    def test_preflight_reports_missing_package_and_honours_skip_flag(self):
        buffer = StringIO()
        with patch.object(manage, 'missing_requirements', return_value=[('django-ckeditor-5', '==0.2.20')]):
            with patch.dict(os.environ, {manage.SKIP_PREFLIGHT_ENV: ''}, clear=False):
                missing = manage._preflight_requirements(stream=buffer)

        self.assertEqual(missing, [('django-ckeditor-5', '==0.2.20')])
        message = buffer.getvalue()
        self.assertIn('django-ckeditor-5==0.2.20', message)
        self.assertIn('requirements.txt', message)
        self.assertIn(sys.executable, message)

        buffer = StringIO()
        with patch.object(manage, 'missing_requirements', return_value=[('django-ckeditor-5', '==0.2.20')]):
            with patch.dict(os.environ, {manage.SKIP_PREFLIGHT_ENV: '1'}, clear=False):
                self.assertEqual(manage._preflight_requirements(stream=buffer), [])
        self.assertEqual(buffer.getvalue(), '')
