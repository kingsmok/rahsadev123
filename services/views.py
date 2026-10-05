from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import ServicePackage, PortfolioItem, ServiceRequest


def services(request):
    """صفحه خدمات طراحی وب سایت: تعرفه‌ها، مراحل کار، نمونه کارها و فرم درخواست."""
    packages = ServicePackage.objects.filter(is_active=True)
    portfolio = PortfolioItem.objects.filter(is_active=True)
    context = {
        'packages': packages,
        'portfolio': portfolio,
    }
    return render(request, 'services/services.html', context)


@require_http_methods(['POST'])
def request_service(request):
    """ثبت درخواست مشاوره / سفارش طراحی سایت (Ajax)."""
    full_name = (request.POST.get('full_name') or '').strip()
    phone = (request.POST.get('phone') or '').strip()
    message = (request.POST.get('message') or '').strip()

    if not full_name or not phone or not message:
        return JsonResponse({'success': False, 'message': 'نام، شماره تماس و توضیحات پروژه الزامی است.'})

    package = None
    package_id = request.POST.get('package')
    if package_id:
        try:
            package = ServicePackage.objects.get(pk=package_id, is_active=True)
        except (ServicePackage.DoesNotExist, ValueError):
            package = None

    ServiceRequest.objects.create(
        full_name=full_name,
        phone=phone,
        email=(request.POST.get('email') or '').strip(),
        package=package,
        project_type=(request.POST.get('project_type') or '').strip(),
        budget=(request.POST.get('budget') or '').strip(),
        message=message,
    )
    return JsonResponse({'success': True, 'message': 'درخواست شما با موفقیت ثبت شد. کارشناسان ما به‌زودی با شما تماس می‌گیرند.'})
