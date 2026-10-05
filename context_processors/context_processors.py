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
