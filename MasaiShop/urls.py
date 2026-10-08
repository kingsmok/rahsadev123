from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from . import settings
from product import views
from django.views.generic import RedirectView, TemplateView
from django.contrib.sitemaps.views import sitemap
from django.templatetags.static import static as static_url
from core.sitemaps import (
    ProductSitemap, CategorySitemap, BrandSitemap, ArticleSitemap,
    StaticPageSitemap, SectionSitemap,
)
from core import views as core_views
from dashboard.admin_views import admin_home

# هندلر خطاهای سفارشی (قالب اختصاصی + noindex)
handler400 = 'core.views.custom_400'
handler403 = 'core.views.custom_403'
handler404 = 'core.views.custom_404'
handler500 = 'core.views.custom_500'

urlpatterns = [
    # Browsers and crawlers still probe this conventional root URL even when
    # the HTML head already declares the PNG favicon.
    path('favicon.ico', RedirectView.as_view(url=static_url('favicon.ico'), permanent=True), name='favicon'),
    path('admin/', admin.site.urls),
    path('admin-panel/', admin_home, name='admin_home'),
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
    # redirect urls
    path('products/category/', views.redirect_to_home, name='redirect_to_home'),
    path('products/brand/', views.redirect_to_home, name='redirect_to_home'),
    path('blog/category/', views.redirect_to_home, name='redirect_to_home'),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
