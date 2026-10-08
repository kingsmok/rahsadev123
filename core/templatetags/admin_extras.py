"""برچسب‌های کمکی مخصوص پوستهٔ Django Admin فایل‌مارکت."""
from django import template
from django.db.models import Sum

register = template.Library()


@register.inclusion_tag('admin/includes/quick_stats.html')
def admin_quick_stats():
    """نوار شاخص بالای صفحهٔ خانهٔ ادمین.

    فقط شمارش‌های سبک انجام می‌شود تا باز شدن صفحهٔ ادمین کند نشود؛ آمار
    تحلیلی کامل در پنل اختصاصی `/admin-panel/` قرار دارد.
    """
    from cart.models import Order
    from django.contrib.auth import get_user_model
    from product.models import Product
    from services.models import ServiceRequest

    paid = Order.objects.filter(status__in=('paid', 'processing', 'shipped', 'delivered'))
    revenue = paid.aggregate(total=Sum('final_price'))['total'] or 0

    return {
        'orders_count': Order.objects.count(),
        'revenue_total': revenue,
        'products_count': Product.objects.count(),
        'published_products': Product.objects.filter(status='published').count(),
        'new_service_requests': ServiceRequest.objects.filter(status='new').count(),
        'pending_orders': Order.objects.filter(status='pending').count(),
        'users_count': get_user_model().objects.count(),
    }
