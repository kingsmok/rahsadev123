# -*- coding: utf-8 -*-
"""نقشه سایت XML — همه بخش‌های عمومی سایت با lastmod و تصویر.

ساختار: محصولات، دسته‌بندی‌ها، برندها، مقالات، صفحات ثابت و صفحات اصلی.
تصاویر محصولات به‌صورت افزونه Image Sitemap افزوده می‌شوند.
"""
from django.contrib.sitemaps import Sitemap
from blog.models import Article
from pages.models import StaticPage
from product.models import Product, ProductBrand, ProductCategory
from services.models import PortfolioItem


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        return Product.objects.filter(status='published').order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at or obj.created_at

    def location(self, obj):
        return f'/products/{obj.pid}/{obj.slug}/'

    def get_urls(self, page=1, site=None, protocol=None, **kwargs):
        urls = super().get_urls(page=page, site=site, protocol=protocol, **kwargs)
        for entry in urls:
            img = getattr(entry.get('item'), 'image', None)
            if img and img:
                entry['image'] = '%s://%s%s' % (protocol or 'http', site.domain if site else '', img.url)
        return urls


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return ProductCategory.objects.all().order_by('id')

    def location(self, obj):
        return f'/products/category/{obj.slug}/'


class BrandSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return ProductBrand.objects.all().order_by('id')

    def location(self, obj):
        return f'/products/brand/{obj.slug}/'


class ArticleSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Article.objects.filter(status='published').order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at or obj.created_at

    def location(self, obj):
        return f'/blog/{obj.slug}/'

    def get_urls(self, page=1, site=None, protocol=None, **kwargs):
        urls = super().get_urls(page=page, site=site, protocol=protocol, **kwargs)
        for entry in urls:
            img = getattr(entry.get('item'), 'image', None)
            if img and img:
                entry['image'] = '%s://%s%s' % (protocol or 'http', site.domain if site else '', img.url)
        return urls


class StaticPageSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return StaticPage.objects.filter(is_published=True).order_by('id')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return f'/pages/{obj.slug}/'


class PortfolioSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return PortfolioItem.objects.filter(is_active=True).order_by('id')

    def location(self, obj):
        return '/services/'


class SectionSitemap(Sitemap):
    """صفحات اصلی سایت (خانه، فروشگاه، وبلاگ، خدمات و...)."""

    def items(self):
        return [
            ('/', 1.0, 'daily'),
            ('/products/', 0.9, 'daily'),
            ('/products/discount_product/', 0.7, 'daily'),
            ('/blog/', 0.8, 'daily'),
            ('/services/', 0.8, 'weekly'),
            ('/contact/', 0.6, 'monthly'),
            ('/about/', 0.6, 'monthly'),
        ]

    def location(self, obj):
        return obj[0]

    def priority(self, obj):
        return obj[1]

    def changefreq(self, obj):
        return obj[2]
