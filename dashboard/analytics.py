"""آمار، نمودارها و هشدارهای داشبورد مدیریت (`/admin-panel/`).

این ماژول تنها داده می‌خواند و هیچ نوشتنی روی پایگاه داده انجام نمی‌دهد تا
بتوان با خیال راحت آن را در تست‌ها و در صفحه داشبورد صدا زد.

قراردادها:
* همه بازه‌های زمانی بر پایه منطقه زمانی فعال پروژه (Asia/Tehran) محاسبه
  می‌شوند و برچسب نمودارها به تاریخ شمسی تبدیل می‌شود.
* «فروش» فقط سفارش‌های با وضعیت ``paid`` است؛ سفارش‌های در انتظار پرداخت در
  آمار درآمد لحاظ نمی‌شوند ولی در تفکیک وضعیت‌ها دیده می‌شوند.
"""
from datetime import datetime, time, timedelta

import jdatetime
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from blog.models import Article
from cart.models import Coupon, Order, OrderItem
from core.models import ContactUs, NewsletterSubscriber, Redirect
from downloads.models import DownloadToken
from payments.models import PaymentTransaction
from product.models import PRODUCT_TYPES, Product, ProductCategory
from services.models import PortfolioItem, ServicePackage, ServiceRequest

# بازه‌های قابل انتخاب در داشبورد: (تعداد روز، برچسب فارسی)
RANGE_CHOICES = (
    (7, '۷ روز اخیر'),
    (30, '۳۰ روز اخیر'),
    (90, '۹۰ روز اخیر'),
    (365, 'یک سال اخیر'),
)
DEFAULT_RANGE_DAYS = 30
LOW_STOCK_THRESHOLD = 5
PAID_STATUSES = ('paid', 'processing', 'shipped', 'delivered')


def resolve_range_days(raw):
    """مقدار انتخاب‌شده کاربر را به یکی از بازه‌های مجاز نگاشت می‌کند."""
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_RANGE_DAYS
    allowed = {days_option for days_option, _label in RANGE_CHOICES}
    return days if days in allowed else DEFAULT_RANGE_DAYS


def _current_timezone():
    return timezone.get_current_timezone()


def window_start(days, reference=None):
    """آغاز روزِ ``days`` روز پیش (به وقت تهران) را برمی‌گرداند."""
    now = timezone.localtime(reference or timezone.now(), _current_timezone())
    first_day = (now - timedelta(days=days - 1)).date()
    return timezone.make_aware(datetime.combine(first_day, time.min), _current_timezone())


def jalali_label(value):
    """تبدیل تاریخ/دیت‌تایم میلادی به برچسب کوتاه شمسی (مثلاً ۰۷/۱۵)."""
    if value is None:
        return ''
    date = value.date() if isinstance(value, datetime) else value
    return jdatetime.date.fromgregorian(date=date).strftime('%m/%d')


def jalali_full(value):
    if value is None:
        return ''
    date = value.date() if isinstance(value, datetime) else value
    return jdatetime.date.fromgregorian(date=date).strftime('%Y/%m/%d')


def _paid_orders(start=None, end=None):
    queryset = Order.objects.filter(status__in=PAID_STATUSES)
    if start is not None:
        queryset = queryset.filter(created_at__gte=start)
    if end is not None:
        queryset = queryset.filter(created_at__lt=end)
    return queryset


def _aggregate(queryset, field='final_price'):
    return queryset.aggregate(total=Sum(field), count=Count('id'))


def revenue_series(days):
    """درآمد و تعداد سفارش به تفکیک روز، با پرکردن روزهای بدون فروش."""
    start = window_start(days)
    rows = (
        _paid_orders(start)
        .annotate(day=TruncDate('created_at', tzinfo=_current_timezone()))
        .values('day')
        .annotate(revenue=Sum('final_price'), orders=Count('id'))
        .order_by('day')
    )
    per_day = {row['day']: row for row in rows}

    series = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).date()
        row = per_day.get(day)
        series.append({
            'date': day,
            'label': jalali_label(day),
            'revenue': int(row['revenue'] or 0) if row else 0,
            'orders': int(row['orders'] or 0) if row else 0,
        })
    return series


def _window_kpis(start, end):
    paid = _aggregate(_paid_orders(start, end))
    downloads = DownloadToken.objects.filter(created_at__gte=start, created_at__lt=end)
    return {
        'revenue': int(paid['total'] or 0),
        'paid_orders': int(paid['count'] or 0),
        'all_orders': Order.objects.filter(created_at__gte=start, created_at__lt=end).count(),
        'new_users': get_user_model().objects.filter(date_joined__gte=start, date_joined__lt=end).count(),
        'downloads': int(downloads.aggregate(total=Sum('download_count'))['total'] or 0),
        'failed_payments': PaymentTransaction.objects.filter(
            status='failed', created_at__gte=start, created_at__lt=end
        ).count(),
    }


def _delta_percent(current, previous):
    """درصد تغییر نسبت به دوره قبل؛ وقتی دوره قبل صفر است None برمی‌گردد."""
    if not previous:
        return None
    return round(((current - previous) / previous) * 100, 1)


def kpis(days):
    """شاخص‌های کلیدی بازه انتخابی به‌همراه مقایسه با دوره مشابه قبلی."""
    start = window_start(days)
    now = timezone.now()
    previous_start = start - timedelta(days=days)
    current = _window_kpis(start, now)
    previous = _window_kpis(previous_start, start)

    current['avg_order_value'] = (
        round(current['revenue'] / current['paid_orders']) if current['paid_orders'] else 0
    )
    current['conversion'] = (
        round((current['paid_orders'] / current['all_orders']) * 100, 1) if current['all_orders'] else 0.0
    )
    current['deltas'] = {
        key: _delta_percent(current[key], previous[key])
        for key in ('revenue', 'paid_orders', 'new_users', 'downloads')
    }
    current['previous'] = previous
    return current


def order_status_breakdown():
    """تفکیک همه سفارش‌ها بر اساس وضعیت، برای نمودار دونات."""
    counts = dict(Order.objects.values_list('status').annotate(total=Count('id')))
    breakdown = []
    for value, label in Order.ORDER_STATUS:
        breakdown.append({'value': value, 'label': label, 'count': int(counts.get(value, 0))})
    return breakdown


def gateway_breakdown(days):
    """عملکرد درگاه‌های پرداخت در بازه انتخابی."""
    start = window_start(days)
    rows = (
        PaymentTransaction.objects.filter(created_at__gte=start)
        .values('gateway')
        .annotate(
            total=Count('id'),
            paid=Count('id', filter=Q(status='paid')),
            failed=Count('id', filter=Q(status='failed')),
            revenue=Sum('amount', filter=Q(status='paid')),
        )
        .order_by('-revenue')
    )
    labels = dict(PaymentTransaction.GATEWAYS)
    breakdown = []
    for row in rows:
        attempts = int(row['total'] or 0)
        paid = int(row['paid'] or 0)
        breakdown.append({
            'value': row['gateway'],
            'label': labels.get(row['gateway'], row['gateway']),
            'attempts': attempts,
            'paid': paid,
            'failed': int(row['failed'] or 0),
            'revenue': int(row['revenue'] or 0),
            'success_rate': round((paid / attempts) * 100, 1) if attempts else 0.0,
        })
    return breakdown


def product_type_breakdown(days, limit=6):
    """سهم هر نوع محصول دیجیتال از درآمد بازه انتخابی."""
    start = window_start(days)
    rows = (
        OrderItem.objects.filter(order__status__in=PAID_STATUSES, order__created_at__gte=start)
        .values('product__product_type')
        .annotate(revenue=Sum('total_price'), units=Sum('quantity'))
        .order_by('-revenue')[:limit]
    )
    labels = dict(PRODUCT_TYPES)
    return [
        {
            'value': row['product__product_type'],
            'label': labels.get(row['product__product_type'], row['product__product_type'] or 'نامشخص'),
            'revenue': int(row['revenue'] or 0),
            'units': int(row['units'] or 0),
        }
        for row in rows
    ]


def top_products(days, limit=6):
    """پرفروش‌ترین فایل‌های بازه انتخابی."""
    start = window_start(days)
    rows = (
        OrderItem.objects.filter(order__status__in=PAID_STATUSES, order__created_at__gte=start)
        .values('product_id', 'product__title', 'product__slug')
        .annotate(revenue=Sum('total_price'), units=Sum('quantity'))
        .order_by('-revenue')[:limit]
    )
    best_revenue = rows[0]['revenue'] if rows else 0
    return [
        {
            'product_id': row['product_id'],
            'title': row['product__title'] or 'محصول حذف‌شده',
            'slug': row['product__slug'] or '',
            'revenue': int(row['revenue'] or 0),
            'units': int(row['units'] or 0),
            'share': round((row['revenue'] / best_revenue) * 100) if best_revenue else 0,
        }
        for row in rows
    ]


def low_stock_products(limit=6):
    """فایل‌های دارای لایسنس محدود که موجودی‌شان رو به پایان است."""
    return list(
        Product.objects.filter(is_unlimited=False, stock_count__lte=LOW_STOCK_THRESHOLD)
        .order_by('stock_count', '-sales_count')[:limit]
    )


def products_without_asset(limit=6):
    """محصولات منتشرشده‌ای که هنوز فایل قابل دانلود ندارند."""
    return list(
        Product.objects.filter(status='published', digital_asset__isnull=True)
        .order_by('-created_at')[:limit]
    )


def pending_actions():
    """صف کارهای نیمه‌تمام؛ برای کارت «نیازمند رسیدگی»."""
    return {
        'pending_orders': Order.objects.filter(status='pending').count(),
        'failed_payments': PaymentTransaction.objects.filter(status='failed').count(),
        'new_service_requests': ServiceRequest.objects.filter(status='new').count(),
        'draft_articles': Article.objects.filter(status='draft').count(),
        'draft_products': Product.objects.filter(status='draft').count(),
        'unpublished_comments': Product.objects.filter(product_comments__status='draft').distinct().count(),
        'new_messages': ContactUs.objects.count(),
        'active_coupons': Coupon.objects.filter(is_active=True).count(),
    }


def catalogue_stats():
    """آمار کلی محتوا و کاربران برای کارت‌های خلاصه."""
    return {
        'products': Product.objects.count(),
        'published_products': Product.objects.filter(status='published').count(),
        'articles': Article.objects.count(),
        'categories': ProductCategory.objects.count(),
        'users': get_user_model().objects.count(),
        'subscribers': NewsletterSubscriber.objects.count(),
        'redirects': Redirect.objects.filter(is_active=True).count(),
        'packages': ServicePackage.objects.count(),
        'portfolio': PortfolioItem.objects.count(),
        'download_tokens': DownloadToken.objects.count(),
    }
