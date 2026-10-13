from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from core.throttling import get_throttle
from .forms import ServiceRequestForm
from .models import PortfolioItem, ServicePackage


def services(request):
    """صفحه خدمات طراحی وب سایت: تعرفه‌ها، مراحل کار، نمونه کارها و فرم درخواست."""
    packages = ServicePackage.objects.filter(is_active=True)
    portfolio = PortfolioItem.objects.filter(is_active=True)
    return render(request, 'services/services.html', {
        'packages': packages,
        'portfolio': portfolio,
    })


@require_POST
def request_service(request):
    """ثبت درخواست مشاوره / سفارش طراحی سایت با اعتبارسنجی سمت سرور."""
    form = ServiceRequestForm(request.POST)

    # Public, unauthenticated and expensive to triage: cap how many requests one
    # visitor can submit in a window.
    throttle = get_throttle('service_request')
    identity = form.data.get('phone', '')
    if throttle.is_throttled(request, identity):
        throttle.record(request, identity)
        return JsonResponse({
            'success': False,
            'message': 'تعداد درخواست‌های شما زیاد است. لطفاً کمی بعد دوباره تلاش کنید.',
        }, status=429)

    if not form.is_valid():
        errors = [error for field_errors in form.errors.values() for error in field_errors]
        return JsonResponse({
            'success': False,
            'message': errors[0] if errors else 'اطلاعات فرم معتبر نیست.',
            'errors': form.errors.get_json_data(),
        }, status=400)

    throttle.record(request, identity)
    form.save()
    return JsonResponse({
        'success': True,
        'message': 'درخواست شما با موفقیت ثبت شد. کارشناسان ما به‌زودی با شما تماس می‌گیرند.',
    })
