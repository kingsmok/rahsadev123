import os
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from .models import DigitalAsset, Product, ProductCategory

class ProductFlowTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('seller', password='safe-pass-123')
        self.category=ProductCategory.objects.create(title='فایل', slug='file')
        self.product=Product.objects.create(vendor=self.user,title='فایل تست',slug='test-file',description='توضیح',price=1000,stock_count=10)
        self.product.category.add(self.category)
    def test_detail_and_listing(self):
        self.assertEqual(self.client.get('/products/').status_code, 200)
        self.assertEqual(self.client.get(f'/products/{self.product.pid}/{self.product.slug}/').status_code, 200)
    def test_search(self):
        self.assertEqual(self.client.get('/products/product_search/?search=تست').status_code, 200)

    def test_product_routes_do_not_accept_trailing_garbage(self):
        response = self.client.get(f'/products/{self.product.pid}/{self.product.slug}/unexpected/')
        self.assertEqual(response.status_code, 404)

    def test_product_canonical_drops_tracking_parameters(self):
        response = self.client.get(
            f'/products/{self.product.pid}/{self.product.slug}/?utm_source=test&campaign=launch'
        )
        self.assertContains(
            response,
            f'<link rel="canonical" href="http://testserver/products/{self.product.pid}/{self.product.slug}/">',
            html=True,
        )

    def test_product_price_cannot_be_negative_in_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(
                    vendor=self.user,
                    title='فایل با قیمت نامعتبر',
                    slug='invalid-price-file',
                    description='توضیح',
                    price=-1,
                )

    def test_draft_product_is_not_publicly_accessible(self):
        draft = Product.objects.create(
            vendor=self.user,
            title='فایل پیش‌نویس',
            slug='draft-file',
            description='این محصول نباید عمومی باشد',
            price=1000,
            status='draft',
        )
        response = self.client.get(f'/products/{draft.pid}/{draft.slug}/')
        self.assertEqual(response.status_code, 404)


class PrivateDigitalAssetStorageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('private-file-owner', password='safe-pass-123')
        self.temp_media = tempfile.TemporaryDirectory()
        self.temp_private = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.temp_media.name,
            PRIVATE_MEDIA_ROOT=self.temp_private.name,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.temp_media.cleanup)
        self.addCleanup(self.temp_private.cleanup)

    def test_paid_asset_is_written_outside_public_media_root(self):
        product = Product.objects.create(
            vendor=self.user,
            title='فایل خصوصی',
            slug='private-file',
            description='فایل فروشی خصوصی',
            price=1000,
        )
        asset = DigitalAsset.objects.create(
            product=product,
            file=SimpleUploadedFile('paid-file.zip', b'private-download-content'),
        )

        self.assertTrue(asset.file.path.startswith(self.temp_private.name))
        self.assertTrue(os.path.isfile(asset.file.path))
        self.assertFalse(os.path.exists(os.path.join(self.temp_media.name, asset.file.name)))
