from django.contrib.sitemaps import Sitemap
from product.models import Product, ProductCategory
from blog.models import Article, Category
from pages.models import StaticPage
class ProductSitemap(Sitemap):
    changefreq='weekly'; priority=.8
    def items(self): return Product.objects.filter(status='published')
    def location(self,obj): return f'/products/{obj.pid}/{obj.slug}/'
class CategorySitemap(Sitemap):
    changefreq='weekly'; priority=.7
    def items(self): return ProductCategory.objects.all()
    def location(self,obj): return f'/products/category/{obj.slug}/'
class ArticleSitemap(Sitemap):
    changefreq='weekly'; priority=.7
    def items(self): return Article.objects.filter(status='published')
    def location(self,obj): return f'/blog/{obj.slug}/'
class PageSitemap(Sitemap):
    changefreq='monthly'; priority=.5
    def items(self): return StaticPage.objects.filter(is_published=True)
    def location(self,obj): return f'/pages/{obj.slug}/'
