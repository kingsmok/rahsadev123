import os
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from .models import DigitalAsset, Product, ProductCategory, ProductComment

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


class ProductCommentThrottleTests(TestCase):
    """Public comment endpoint must resist automated flooding."""

    def setUp(self):
        self.user = User.objects.create_user('seller2', password='safe-pass-123')
        self.product = Product.objects.create(
            vendor=self.user, title='فایل دیدگاه', slug='comment-file',
            description='توضیح', price=1000,
        )
        self.url = f'/products/{self.product.pid}/{self.product.slug}/'

    def _post(self, author):
        self.client.force_login(author)
        return self.client.post(
            self.url, data='{"body": "دیدگاه تست"}',
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_comments_are_rate_limited_per_user(self):
        author = User.objects.create_user('commenter', password='Safe-pass-123!')
        with override_settings(PUBLIC_WRITE_RATE_LIMITS={'comment': (3, 100)}):
            from django.core.cache import cache
            cache.clear()

            self.client.force_login(author)
            for _ in range(3):
                response = self.client.post(
                    self.url, data='{"body": "دیدگاه تست"}',
                    content_type='application/json',
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(response.status_code, 200, response.content)

            blocked = self.client.post(
                self.url, data='{"body": "دیدگاه اضافی"}',
                content_type='application/json',
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(ProductComment.objects.filter(author=author).count(), 3)

    def test_comment_requires_authentication(self):
        response = self.client.post(
            self.url, data='{"body": "بدون ورود"}',
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ProductComment.objects.count(), 0)


class CommentModerationTests(TestCase):
    """دیدگاه تا پیش از تأیید مدیر نباید عمومی دیده شود."""

    def setUp(self):
        self.user = User.objects.create_user('seller3', password='safe-pass-123')
        self.product = Product.objects.create(
            vendor=self.user, title='فایل نظارت', slug='moderated-file',
            description='توضیح', price=1000,
        )
        self.author = User.objects.create_user('mod-author', password='Safe-pass-123!')
        self.url = f'/products/{self.product.pid}/{self.product.slug}/'
        self.client.force_login(self.author)

    def _post_comment(self):
        return self.client.post(
            self.url, data='{"body": "دیدگاه در انتظار"}',
            content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_new_comment_is_pending_and_hidden_until_approved(self):
        response = self._post_comment()
        self.assertEqual(response.status_code, 200, response.content)
        comment = ProductComment.objects.get(author=self.author)
        self.assertEqual(comment.status, 'pending')

        self.client.logout()
        page = self.client.get(self.url)
        self.assertNotContains(page, 'دیدگاه در انتظار')

        comment.status = 'published'
        comment.save(update_fields=['status'])
        page = self.client.get(self.url)
        self.assertContains(page, 'دیدگاه در انتظار')


class ListingFilterStateTests(TestCase):
    """Filters must survive pagination and stay visible on the search page."""

    def setUp(self):
        from django.contrib.auth.models import User as _User

        from product.models import ProductBrand

        vendor = _User.objects.create_user('filter-vendor', password='Safe-pass-123!')
        self.brand = ProductBrand.objects.create(title='سازنده فیلتر', slug='filter-brand')
        for index in range(12):
            product = Product.objects.create(
                vendor=vendor, title=f'قالب فیلتر {index}', slug=f'filter-item-{index}', description='-',
                price=1000 + index, product_type='template' if index % 2 else 'plugin',
            )
            product.brand.add(self.brand)

    def test_pagination_keeps_every_selected_type(self):
        response = self.client.get('/products/', {'type': ['template', 'plugin']})

        querystring = response.context['querystring']
        self.assertIn('type=template', querystring)
        self.assertIn('type=plugin', querystring)

    def test_search_page_keeps_the_brand_filter_ticked(self):
        response = self.client.get('/products/product_search/', {'search': 'قالب', 'brand': str(self.brand.pk)})

        self.assertEqual(response.context['selected_brands'], [self.brand.pk])
        self.assertContains(response, f'id="brand_{self.brand.pk}" checked')


class MalformedJsonInputTests(TestCase):
    """Valid-but-unexpected JSON must be a 400, never an unhandled 500."""

    def setUp(self):
        from django.contrib.auth.models import User as _User

        self.user = _User.objects.create_user('json-fuzz', password='Safe-pass-123!')
        self.product = Product.objects.create(
            vendor=self.user, title='فایل دیدگاه JSON', slug='json-comment', description='-', price=1000,
        )
        self.detail = f'/products/{self.product.pid}/{self.product.slug}/'

    def test_comment_endpoint_rejects_non_object_json(self):
        self.client.force_login(self.user)
        for body in ('[]', '"x"', '5', 'null', '{"body": 5}', '{"body": {"a": 1}}'):
            response = self.client.post(self.detail, data=body, content_type='application/json')
            self.assertEqual(response.status_code, 400, body)

    def test_comment_endpoint_rejects_non_object_json_from_anonymous_users(self):
        response = self.client.post(self.detail, data='[]', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_newsletter_rejects_non_object_json_and_non_string_email(self):
        for body in ('[]', '"x"', '5', 'null'):
            response = self.client.post('/newsletter/subscribe/', data=body, content_type='application/json')
            self.assertEqual(response.status_code, 400, body)
        for body in ('{"email": 5}', '{"email": ["a@b.co"]}'):
            response = self.client.post('/newsletter/subscribe/', data=body, content_type='application/json')
            self.assertEqual(response.status_code, 200, body)
            self.assertFalse(response.json()['ok'])
