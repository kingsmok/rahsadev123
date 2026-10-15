from django.shortcuts import get_object_or_404, render

from .models import StaticPage


def detail(request, slug):
    # مدیران پیش‌نویس‌ها را هم می‌بینند تا چیدمان و کد HTML را پیش از انتشار بررسی کنند.
    pages = StaticPage.objects.all() if request.user.is_staff else StaticPage.objects.filter(is_published=True)
    page = get_object_or_404(pages, slug=slug)
    # فهرست سایر صفحات راهنما برای ناوبری کناری
    other_pages = StaticPage.objects.filter(is_published=True).only('title', 'slug')
    return render(request, 'pages/detail.html', {
        'page': page,
        'other_pages': other_pages,
    })
