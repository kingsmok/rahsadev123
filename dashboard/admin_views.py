"""صفحه‌های مدیریت (پنل اختصاصی `/admin-panel/`).

این صفحه‌ها جدا از Django Admin هستند و برای مشاهده سریع وضعیت فروشگاه،
نمودارها و کارهای نیمه‌تمام طراحی شده‌اند. همه با `staff_member_required`
محافظت می‌شوند.
"""
import csv
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from blog.models import Article
from cart.models import Order
from core.models import Redirect
from downloads.models import DownloadToken
from payments.models import GatewaySettings, PaymentTransaction
from product.models import Product
from services.models import PortfolioItem, ServicePackage, ServiceRequest

from . import analytics


def _chart_payload(revenue_series, status_breakdown, type_breakdown):
    """دادهٔ نمودارها را به شکل JSON-پذیر (بدون date) آماده می‌کند."""
    return {
        'revenue': {
            'labels': [point['label'] for point in revenue_series],
            'values': [point['revenue'] for point in revenue_series],
            'orders': [point['orders'] for point in revenue_series],
        },
        'status': {
            'labels': [item['label'] for item in status_breakdown],
            'values': [item['count'] for item in status_breakdown],
        },
        'productType': {
            'labels': [item['label'] for item in type_breakdown],
            'values': [item['revenue'] for item in type_breakdown],
        },
    }


def _sidebar_context():
    """کلیدهایی که سایدبار پنل (`admin_panel_base.html`) برای شمارنده‌ها لازم دارد.

    همهٔ صفحه‌های پنل باید این کلیدها را به قالب بدهند تا نشانگرهای کنار منو
    (در انتظار، کاتالوگ، ریدایرکت) خالی نمانند.
    """
    return {
        'pending': analytics.pending_actions(),
        'catalogue': analytics.catalogue_stats(),
        'redirects_count': Redirect.objects.filter(is_active=True).count(),
        'today_jalali': analytics.jalali_full(timezone.localtime(timezone.now())),
    }


@staff_member_required
def admin_home(request):
    range_days = analytics.resolve_range_days(request.GET.get('range'))
    revenue_series = analytics.revenue_series(range_days)
    status_breakdown = analytics.order_status_breakdown()
    type_breakdown = analytics.product_type_breakdown(range_days)
    gateway_breakdown = analytics.gateway_breakdown(range_days)

    context = {
        'range_days': range_days,
        'range_choices': analytics.RANGE_CHOICES,
        'kpis': analytics.kpis(range_days),
        'revenue_series': revenue_series,
        'status_breakdown': status_breakdown,
        'type_breakdown': type_breakdown,
        'gateway_breakdown': gateway_breakdown,
        'top_products': analytics.top_products(range_days),
        'low_stock_products': analytics.low_stock_products(),
        'products_without_asset': analytics.products_without_asset(),
        'chart_data': _chart_payload(revenue_series, status_breakdown, type_breakdown),
        'recent_orders': Order.objects.select_related('user').order_by('-created_at')[:10],
        'recent_payments': PaymentTransaction.objects.select_related('order').order_by('-created_at')[:8],
        'service_requests': ServiceRequest.objects.select_related('package').order_by('-created_at')[:6],
        'recent_downloads': DownloadToken.objects.select_related('user', 'product').order_by('-created_at')[:6],
        'recent_articles': Article.objects.order_by('-created_at')[:5],
        'gateways': GatewaySettings.objects.all(),
        **_sidebar_context(),
        'window_from': analytics.jalali_full(analytics.window_start(range_days)),
        'window_to': analytics.jalali_full(timezone.localtime(timezone.now())),
        'week_ago_orders': Order.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count(),
    }
    return render(request, 'dashboard/admin_home.html', context)


@staff_member_required
def admin_export_orders(request):
    """خروجی CSV سفارش‌ها (با BOM تا در اکسل فارسی درست نمایش داده شود)."""
    days = analytics.resolve_range_days(request.GET.get('range'))
    start = analytics.window_start(days)
    orders = (
        Order.objects.select_related('user')
        .filter(created_at__gte=start)
        .order_by('-created_at')
    )

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f'masaishop-orders-{days}d.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow([
        'شماره سفارش', 'کاربر', 'ایمیل', 'تاریخ شمسی', 'مبلغ کل',
        'تخفیف', 'مبلغ پرداختی', 'وضعیت', 'درگاه', 'کد رهگیری',
    ])
    for order in orders:
        payment = order.payments.filter(status='paid').order_by('-created_at').first()
        writer.writerow([
            order.order_number,
            order.user.get_username(),
            order.user.email or '',
            analytics.jalali_full(order.created_at),
            order.total_price,
            order.coupon_discount,
            order.final_price,
            order.get_status_display(),
            payment.get_gateway_display() if payment else '',
            payment.ref_id if payment else '',
        ])
    return response


@staff_member_required
def admin_health(request):
    """بررسی سریع سلامت فروشگاه: داده‌های ناقص و کارهای نیمه‌تمام."""
    context = {
        'products_without_asset': Product.objects.filter(
            status='published', digital_asset__isnull=True
        ).order_by('-created_at'),
        'products_without_image': Product.objects.filter(
            status='published', image=''
        ).order_by('-created_at')[:30],
        'products_without_seo': Product.objects.filter(
            status='published', meta_description=''
        ).order_by('-created_at')[:30],
        'draft_products': Product.objects.filter(status='draft').order_by('-created_at'),
        'draft_articles': Article.objects.filter(status='draft').order_by('-created_at'),
        'low_stock': analytics.low_stock_products(limit=20),
        'pending_orders': Order.objects.filter(status='pending').order_by('-created_at'),
        'failed_payments': PaymentTransaction.objects.filter(status='failed').order_by('-created_at')[:30],
        'unconfigured_gateways': [
            gateway for gateway in GatewaySettings.objects.all()
            if gateway.is_enabled and not gateway.is_configured
        ],
        'inactive_packages': ServicePackage.objects.filter(is_active=False),
        'inactive_portfolio': PortfolioItem.objects.filter(is_active=False),
        **_sidebar_context(),
    }
    return render(request, 'dashboard/admin_health.html', context)
