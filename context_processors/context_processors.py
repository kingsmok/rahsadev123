from core.models import SiteSettings
from product.models import ProductCategory, ProductBrand
from cart.models import Cart, CartItem


def shop_func(request):
    site_settings = SiteSettings.objects.first()
    categories = ProductCategory.objects.all()
    brands = ProductBrand.objects.all()

    cart = None
    cart_items = []
    cart_total = 0
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.filter(user=request.user).first()
            if cart:
                cart_items = CartItem.objects.filter(cart=cart).select_related('product')
                cart_total = cart.total_price
        except Exception:
            pass

    return {
        'site_settings': site_settings,
        'site_name': site_settings.site_name if site_settings else 'فایل‌مارکت',
        'categories': categories,
        'brands': brands,

        'cart': cart,
        'cart_items': cart_items,
        'cart_total': cart_total,
    }


# ------------------------------------------------------------------ سئوی خودکار

# مسیرهایی که نباید ایندکس شوند (صفحات خصوصی/تراکنشی/جست‌وجو)
import re as _re

_NOINDEX_PATTERNS = [
    _re.compile(r'^/admin'),
    _re.compile(r'^/account/'),
    _re.compile(r'^/dashboard/'),
    _re.compile(r'^/cart/'),
    _re.compile(r'^/payments/'),
    _re.compile(r'^/downloads/'),
    _re.compile(r'^/ckeditor/'),
    _re.compile(r'^/products/product_search/'),
    _re.compile(r'^/services/request/'),
]


def seo_context(request):
    """سئوی خودکار: canonical تمیز (بدون کوئری‌استرینگ اضافی) + متای robots."""
    # آدرس canonical: فقط مسیر + پارامتر صفحه (برای صفحات ۲ به بعد)
    path = request.path
    canonical = request.build_absolute_uri(path)
    page = request.GET.get('page')
    if page and str(page).isdigit() and int(page) > 1:
        canonical += '?page=%s' % int(page)

    meta_robots = 'index, follow'
    if request.method == 'GET':
        for pattern in _NOINDEX_PATTERNS:
            if pattern.match(path):
                meta_robots = 'noindex, follow'
                break
        # نتیجه‌های جست‌وجو با کوئری
        if request.GET.get('q'):
            meta_robots = 'noindex, follow'

    return {
        'canonical_url': canonical,
        'meta_robots': meta_robots,
    }
