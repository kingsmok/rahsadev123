"""A product's file is either uploaded to the site or delivered from a download link."""
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from cart.models import Order, OrderItem
from downloads.models import DownloadToken
from notifications.models import AdminNotification
from product.admin import DigitalAssetForm
from product.models import DigitalAsset, Product, ProductCategory, missing_file_q

LINK = 'https://dl.example.com/files/Big%20Theme.v2.zip?expires=1700000000&sig=abc'


class _PrivateMediaMixin:
    def setUp(self):
        super().setUp()
        private = tempfile.mkdtemp()
        media = tempfile.mkdtemp()
        override = override_settings(PRIVATE_MEDIA_ROOT=private, MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, private, True)
        self.addCleanup(shutil.rmtree, media, True)


class DigitalAssetModelTests(_PrivateMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        vendor = User.objects.create_user('asset-vendor', password='Safe-pass-123!')
        self.product = Product.objects.create(vendor=vendor, title='قالب بزرگ', slug='big-theme',
                                              description='توضیح', price=1000)

    def test_link_mode_requires_a_link(self):
        with self.assertRaises(ValidationError) as caught:
            DigitalAsset(product=self.product, source=DigitalAsset.SOURCE_LINK).full_clean()
        self.assertIn('external_url', caught.exception.message_dict)

    def test_upload_mode_requires_a_file(self):
        with self.assertRaises(ValidationError) as caught:
            DigitalAsset(product=self.product, source=DigitalAsset.SOURCE_UPLOAD).full_clean()
        self.assertIn('file', caught.exception.message_dict)

    def test_only_web_links_are_accepted(self):
        for bad in ('javascript:alert(1)', 'ftp://files.example.com/a.zip', 'file:///etc/passwd', 'not a url'):
            with self.subTest(bad=bad), self.assertRaises(ValidationError) as caught:
                DigitalAsset(product=self.product, source=DigitalAsset.SOURCE_LINK, external_url=bad).full_clean()
            self.assertIn('external_url', caught.exception.message_dict)

    def test_link_mode_is_valid_without_a_file_and_reads_the_format_from_the_link(self):
        asset = DigitalAsset(product=self.product, source=DigitalAsset.SOURCE_LINK, external_url=LINK)
        asset.full_clean()
        asset.save()
        self.assertEqual(asset.file_type, 'ZIP')
        self.assertTrue(asset.is_deliverable())
        self.assertFalse(Product.objects.filter(missing_file_q(), pk=self.product.pk).exists())

    def test_uploaded_file_still_measures_its_size_and_format(self):
        asset = DigitalAsset(product=self.product)
        asset.file.save('starter-kit.rar', ContentFile(b'x' * 2048), save=True)
        self.assertEqual(asset.file_size, 2048)
        self.assertEqual(asset.file_type, 'RAR')
        self.assertTrue(asset.is_deliverable())

    def test_health_check_counts_empty_uploads_and_links_as_missing(self):
        DigitalAsset.objects.create(product=self.product, source=DigitalAsset.SOURCE_LINK, external_url='')
        self.assertTrue(Product.objects.filter(missing_file_q(), pk=self.product.pk).exists())

    def test_admin_form_stores_the_size_entered_for_a_link(self):
        form = DigitalAssetForm(data={
            'source': 'link', 'external_url': LINK, 'link_size_mb': '250.5', 'version': '2.0',
        }, instance=DigitalAsset(product=self.product))
        self.assertTrue(form.is_valid(), form.errors)
        asset = form.save()
        self.assertEqual(asset.file_size, int(Decimal('250.5') * 1024 * 1024))
        self.assertEqual(asset.file_size_display, '250.5 مگابایت')
        self.assertEqual(DigitalAssetForm(instance=asset).initial['link_size_mb'], 250.5)

    def test_admin_form_explains_which_field_is_missing(self):
        form = DigitalAssetForm(data={'source': 'link'}, instance=DigitalAsset(product=self.product))
        self.assertFalse(form.is_valid())
        self.assertIn('external_url', form.errors)


class LinkDeliveryTests(_PrivateMediaMixin, TestCase):
    """The link is a delivery method only: every entitlement check still applies."""

    def setUp(self):
        super().setUp()
        self.buyer = User.objects.create_user('link-buyer', password='Safe-pass-123!')
        vendor = User.objects.create_user('link-vendor', password='Safe-pass-123!')
        self.product = Product.objects.create(vendor=vendor, title='فایل حجیم', slug='huge-file',
                                              description='توضیح', price=500000)
        self.asset = DigitalAsset.objects.create(product=self.product, source=DigitalAsset.SOURCE_LINK,
                                                 external_url=LINK)
        self.order = Order.objects.create(
            user=self.buyer, total_price=500000, coupon_discount=0, shipping_cost=0, final_price=500000,
            status='paid', items_data={'items': [{'product_id': self.product.pk, 'title': 'فایل حجیم',
                                                  'quantity': 1, 'price': 500000}], 'coupon': None},
        )
        OrderItem.objects.create(order=self.order, product=self.product, title_snapshot='فایل حجیم',
                                 unit_price=500000, quantity=1, total_price=500000)
        self.token = DownloadToken.objects.create(order=self.order, user=self.buyer, product=self.product)
        self.client.force_login(self.buyer)

    def _download(self):
        return self.client.get(f'/downloads/{self.token.token}/')

    def test_buyer_is_sent_to_the_link_and_a_download_is_counted(self):
        response = self._download()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], LINK)
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertIn('no-store', response['Cache-Control'])
        self.token.refresh_from_db()
        self.asset.refresh_from_db()
        self.assertEqual(self.token.download_count, 1)
        self.assertEqual(self.asset.download_count, 1)

    def test_link_is_never_printed_in_pages(self):
        product_page = f'/products/{self.product.pid}/{self.product.slug}/'
        for path in (product_page, '/dashboard/downloads/', f'/dashboard/orders/{self.order.order_number}/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'dl.example.com')
        self.client.logout()
        self.assertNotContains(self.client.get(product_page), 'dl.example.com')

    def test_expired_or_exhausted_tokens_do_not_reveal_the_link(self):
        self.token.expires_at = timezone.now() - timedelta(minutes=1)
        self.token.save(update_fields=['expires_at'])
        response = self._download()
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('dl.example.com', response['Location'])

        self.token.expires_at = timezone.now() + timedelta(days=1)
        self.token.download_count = self.token.max_downloads
        self.token.save(update_fields=['expires_at', 'download_count'])
        self.assertNotIn('dl.example.com', self._download()['Location'])

    def test_refund_withdraws_the_link(self):
        self.order.status = 'refunded'
        self.order.save(update_fields=['status'])
        response = self._download()
        self.assertNotIn('dl.example.com', response['Location'])
        self.token.refresh_from_db()
        self.assertEqual(self.token.download_count, 0)

    def test_someone_else_cannot_use_the_token(self):
        intruder = User.objects.create_user('intruder', password='Safe-pass-123!')
        self.client.force_login(intruder)
        self.assertEqual(self._download().status_code, 404)

    def test_missing_upload_does_not_crash_or_spend_a_download(self):
        self.asset.source = DigitalAsset.SOURCE_UPLOAD
        self.asset.external_url = ''
        self.asset.file.name = 'digital-products/deleted-from-disk.zip'
        with self.assertLogs('product.models', 'WARNING'):
            self.asset.save()

        with self.assertLogs('downloads.views', 'ERROR') as logged:
            response = self._download()

        self.assertIn('قابل تحویل نیست', logged.output[0])

        self.assertRedirects(response, f'/dashboard/orders/{self.order.order_number}/',
                             fetch_redirect_response=False)
        self.token.refresh_from_db()
        self.assertEqual(self.token.download_count, 0)
        alert = AdminNotification.objects.get(kind='system')
        self.assertIn('فایل حجیم', alert.title)
        self.assertEqual(alert.level, 'danger')


class ProductAdminFileChoiceTests(_PrivateMediaMixin, TestCase):
    """The product form offers «آپلود فایل» or «لینک دانلود» and saves either."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('asset-admin', 'a@example.com', 'Safe-pass-123!')
        self.category = ProductCategory.objects.create(title='قالب', slug='templates')
        self.client.force_login(self.admin)

    def _post(self, slug, asset_fields):
        data = {
            'vendor': self.admin.pk, 'title': f'محصول {slug}', 'slug': slug, 'short_description': '',
            'description': '<p>توضیح</p>', 'category': [self.category.pk], 'status': 'published',
            'price': '120000', 'old_price': '', 'stock_count': '0', 'is_unlimited': 'on',
            'product_type': 'template', 'license_type': 'single', 'demo_url': '', 'documentation_url': '',
            'requirements': '', 'operating_system': '', 'support_duration': '', 'update_duration': '',
            'meta_title': '', 'meta_description': '', 'canonical_url': '',
            'custom_html_mode': 'after', 'custom_html': '',
            'digital_asset-TOTAL_FORMS': '1', 'digital_asset-INITIAL_FORMS': '0',
            'digital_asset-MIN_NUM_FORMS': '0', 'digital_asset-MAX_NUM_FORMS': '1',
            'product_images-TOTAL_FORMS': '0', 'product_images-INITIAL_FORMS': '0',
            'product_images-MIN_NUM_FORMS': '0', 'product_images-MAX_NUM_FORMS': '1000',
            '_save': 'ذخیره',
        }
        data.update({f'digital_asset-0-{key}': value for key, value in asset_fields.items()})
        return self.client.post('/admin/product/product/add/', data)

    def _errors(self, response):
        if response.status_code == 302:
            return ''
        context = response.context
        errors = [context['adminform'].form.errors]
        errors += [formset.formset.errors for formset in context['inline_admin_formsets']]
        return repr(errors)

    def test_add_form_offers_both_choices(self):
        response = self.client.get('/admin/product/product/add/')
        self.assertContains(response, 'نحوهٔ تحویل فایل')
        self.assertContains(response, 'value="upload"')
        self.assertContains(response, 'value="link"')
        self.assertContains(response, 'name="digital_asset-0-external_url"')
        self.assertContains(response, 'js/fm-digital-asset.js?v=')

    def test_product_with_a_download_link_is_saved(self):
        response = self._post('linked', {'source': 'link', 'external_url': LINK, 'link_size_mb': '1024',
                                         'version': '3.1'})
        self.assertEqual(response.status_code, 302, self._errors(response))
        asset = Product.objects.get(slug='linked').digital_asset
        self.assertTrue(asset.is_link)
        self.assertEqual(asset.external_url, LINK)
        self.assertEqual(asset.file_size_display, '1.00 گیگابایت')
        self.assertFalse(asset.file)

    def test_link_choice_without_a_link_is_rejected_with_a_clear_error(self):
        response = self._post('broken-link', {'source': 'link', 'external_url': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'آدرس لینک فایل را وارد کنید')
        self.assertFalse(Product.objects.filter(slug='broken-link').exists())

    def test_untouched_file_form_does_not_block_saving_a_product(self):
        response = self._post('no-file-yet', {'source': 'upload', 'external_url': '', 'link_size_mb': ''})
        self.assertEqual(response.status_code, 302, self._errors(response))
        self.assertFalse(DigitalAsset.objects.filter(product__slug='no-file-yet').exists())
