from django.shortcuts import get_object_or_404, render

from .models import StaticPage


def detail(request, slug):
    page = get_object_or_404(StaticPage, slug=slug, is_published=True)
    # فهرست سایر صفحات راهنما برای ناوبری کناری
    other_pages = StaticPage.objects.filter(is_published=True).only('title', 'slug')
    return render(request, 'pages/detail.html', {
        'page': page,
        'other_pages': other_pages,
    })
