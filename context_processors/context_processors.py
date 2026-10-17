from django.db import OperationalError, ProgrammingError

from core.branding import get_brand
from product.models import ProductCategory, ProductBrand
from cart.guest import get_cart
from cart.models import CartItem
from core.social import social_links


def shop_func(request):
    # نام، لوگو و آیکن‌ها از یک منبع واحد (core.branding) می‌آیند تا تغییرشان در
    # «تنظیمات سایت» همزمان در همهٔ قالب‌ها — از جمله ادمین — دیده شود.
    # «site_brand» نامیده شده چون «brand» در صفحهٔ برندهای محصول، متغیر view است.
    site_brand = get_brand(request)
    site_settings = site_brand.settings
    categories = ProductCategory.objects.all()
    brands = ProductBrand.objects.all()

    cart = None
    cart_items = []
    cart_total = 0
    wishlist_count = 0
    try:
        # مهمان هم سبد خرید دارد (سبدِ نشست؛ cart.guest.get_cart).
        cart = get_cart(request)
        if cart:
            # Keep one evaluated, joined collection for both the header and
            # its total. Calling ``cart.total_price`` here issued another
            # query and then one query per product on every rendered page.
            cart_items = list(CartItem.objects.filter(cart=cart).select_related('product'))
            cart_total = sum(item.total_price for item in cart_items)
        if request.user.is_authenticated:
            from dashboard.models import Wishlist

            wishlist_count = Wishlist.objects.filter(user=request.user).count()
    except (OperationalError, ProgrammingError):
        # A request must still render while migrations are being applied
        # and the cart tables do not exist yet.
        pass
    # The drawer total must match the cart page: subtract the applied coupon.
    cart_discount = min(cart.coupon_discount, cart_total) if (cart and cart.coupon_id) else 0

    return {
        'site_settings': site_settings,
        'site_brand': site_brand,
        'site_name': site_brand.name,
        'categories': categories,
        'brands': brands,

        'cart': cart,
        'cart_items': cart_items,
        'cart_total': cart_total,
        'cart_count': len(cart_items),
        'cart_discount': cart_discount,
        'cart_payable': max(0, cart_total - cart_discount),
        'wishlist_count': wishlist_count,
        'social_links': social_links(site_settings),
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
    _re.compile(r'^/ckeditor5/'),
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
