from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from . import settings
from product import views
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from core.sitemaps import (
    ProductSitemap, CategorySitemap, BrandSitemap, ArticleSitemap,
    StaticPageSitemap, SectionSitemap,
)
from core import views as core_views
from dashboard.admin_views import admin_export_orders, admin_health, admin_home

# هندلر خطاهای سفارشی (قالب اختصاصی + noindex)
handler400 = 'core.views.custom_400'
handler403 = 'core.views.custom_403'
handler404 = 'core.views.custom_404'
handler500 = 'core.views.custom_500'

# عنوان و سربرگ ادمین از «تنظیمات سایت» می‌آیند: MasaiShop/admin_branding.py
# (از طریق MasaiShop.apps.FileMarketAdminConfig در INSTALLED_APPS).

urlpatterns = [
    # Browsers and crawlers still probe this conventional root URL even when
    # the HTML head declares the icon.  It follows the icon uploaded in
    # «تنظیمات سایت» with a temporary redirect: the former permanent (301)
    # redirect was cached by browsers forever, pinning the old icon.
    path('favicon.ico', core_views.favicon, name='favicon'),
    path('admin/', admin.site.urls),
    path('admin-panel/', admin_home, name='admin_home'),
    path('admin-panel/export/orders/', admin_export_orders, name='admin_export_orders'),
    path('admin-panel/health/', admin_health, name='admin_health'),
    path('sitemap.xml', sitemap, {'sitemaps': {
        'sections': SectionSitemap,
        'products': ProductSitemap,
        'categories': CategorySitemap,
        'brands': BrandSitemap,
        'articles': ArticleSitemap,
        'pages': StaticPageSitemap,
    }}, name='sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain'), name='robots'),
    path('llms.txt', core_views.llms_txt, name='llms_txt'),
    path('payments/', include('payments.urls')),
    path('downloads/', include('downloads.urls')),
    path('services/', include('services.urls')),
    path('pages/', include('pages.urls')),
    path('', include('core.urls')),
    path('products/', include('product.urls')),
    path('account/', include('accounts.urls')),
    path('blog/', include('blog.urls')),
    path('cart/', include('cart.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    # redirect urls — مسیرهای بدون نامک به فهرست مرتبط می‌روند.
    # /blog/category/ را خودِ اپ blog با 301 به فهرست مقالات می‌فرستد؛
    # تعریف دوباره‌اش اینجا هم غیرقابل‌دسترسی بود (include زودتر match می‌شود)
    # هم نام یکسانِ «redirect_to_home» را سه بار تکرار می‌کرد.
    path('products/category/', views.redirect_to_home, name='redirect_products_category'),
    path('products/brand/', views.redirect_to_home, name='redirect_products_brand'),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
