from django.contrib.auth.models import User
from django.test import TestCase
from .models import Product, ProductCategory

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
