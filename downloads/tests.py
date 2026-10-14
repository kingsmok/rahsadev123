"""Tests for private file delivery."""
from django.contrib.auth.models import User
from django.test import TestCase

from cart.models import Order, OrderItem
from downloads.models import DownloadToken
from product.models import DigitalAsset, Product

class RefundRevokesDownloadTests(TestCase):
    """Downloading must stop once the money has gone back to the customer."""

    def setUp(self):
        from django.core.files.base import ContentFile

        self.buyer = User.objects.create_user('refund-buyer', password='Safe-pass-123!')
        self.buyer.profile.card_number = '1234567890123456'
        self.buyer.profile.save()
        vendor = User.objects.create_user('vendor', password='Safe-pass-123!')
        self.product = Product.objects.create(
            vendor=vendor, title='فایل گران', slug='pricey-file', description='توضیح',
            price=500000,
        )
        self.asset = DigitalAsset.objects.create(product=self.product)
        self.asset.file.save('licence.zip', ContentFile(b'PK-fake-zip-content'), save=True)
        self.order = Order.objects.create(
            user=self.buyer, total_price=500000, coupon_discount=0, shipping_cost=0,
            final_price=500000, status='paid',
            items_data={'items': [{'product_id': self.product.pk, 'title': 'فایل گران',
                                   'quantity': 1, 'price': 500000}], 'coupon': None},
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, title_snapshot='فایل گران',
            unit_price=500000, quantity=1, total_price=500000,
        )
        self.token = DownloadToken.objects.create(
            order=self.order, user=self.buyer, product=self.product,
        )
        self.client.force_login(self.buyer)

    def _download(self):
        return self.client.get(f'/downloads/{self.token.token}/')

    def test_file_is_delivered_while_the_sale_stands(self):
        self.assertEqual(self._download().status_code, 200)

    def test_refunded_order_stops_serving_the_file(self):
        self.order.status = 'refunded'
        self.order.save(update_fields=['status'])

        response = self._download()

        self.assertEqual(response.status_code, 302)
        self.token.refresh_from_db()
        # The entitlement is withdrawn, not consumed: nothing was downloaded.
        self.assertEqual(self.token.download_count, 0)

    def test_cancelled_order_stops_serving_the_file(self):
        self.order.status = 'cancelled'
        self.order.save(update_fields=['status'])

        response = self._download()

        self.assertEqual(response.status_code, 302)
        self.token.refresh_from_db()
        self.assertEqual(self.token.download_count, 0)

    def test_reinstating_the_order_restores_the_download(self):
        self.order.status = 'cancelled'
        self.order.save(update_fields=['status'])
        self.assertEqual(self._download().status_code, 302)

        self.order.status = 'paid'
        self.order.save(update_fields=['status'])
        self.assertEqual(self._download().status_code, 200)
