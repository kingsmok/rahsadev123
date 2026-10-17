import logging

from django.core.cache import cache
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.templatetags.static import static
from django.views.decorators.http import require_safe

from core import branding
from .forms import ContactUsForm
from product.models import ProductBrand, Product
from django.db import models
from .models import Banner
from blog.models import Article
from services.models import ServicePackage
from core.throttling import get_throttle


def _storefront_products(queryset):
    """Load product-card relations once instead of once per card in templates."""
    return queryset.select_related('digital_asset').prefetch_related('brand')


def home(request):
    from product.showcase import showcase_products

    # Banners (ترتیب و اندازه از پنل مدیریت ← بنرها)
    published_banners = Banner.objects.filter(status='published').order_by('order', '-created_at')
    main_sliders = published_banners.filter(banner_type='main_slider')[:5]
    small_banners = published_banners.filter(banner_type='small_banner')[:8]
    large_banners = published_banners.filter(banner_type='large_banner')[:4]
    single_banner = published_banners.filter(banner_type='single_banner').first()

    popular_brands = ProductBrand.objects.all().order_by('-views')[:10]
    # ویترین‌ها از «محصولات ← ویترین‌های صفحهٔ اصلی» قابل تنظیم‌اند؛ پیش‌فرض‌ها
    # همان رفتار قبلی صفحه را حفظ می‌کنند.
    offers_showcase, popular_products = showcase_products('home_offers', 'popular', 9)
    side_showcase, latest_products = showcase_products('home_side', 'latest', 6)
    discounts_showcase, discounted_products = showcase_products('home_discounts', 'discounted', 8)
    bestsellers_showcase, best_selling_products = showcase_products('home_bestsellers', 'best_selling', 7)
    latest_articles = Article.objects.filter(status='published').select_related(
        'author', 'author__profile'
    ).order_by('-created_at')[:5]
    service_packages = ServicePackage.objects.filter(is_active=True)[:3]

    context = {
        'main_sliders': main_sliders,
        'small_banners': small_banners,
        'large_banners': large_banners,
        'single_banner': single_banner,

        'popular_brands': popular_brands,
        'popular_products': popular_products,
        'latest_products': latest_products,
        'latest_articles': latest_articles,
        'discounted_products': discounted_products,
        'best_selling_products': best_selling_products,
        'service_packages': service_packages,

        'offers_showcase': offers_showcase,
        'side_showcase': side_showcase,
        'discounts_showcase': discounts_showcase,
        'bestsellers_showcase': bestsellers_showcase,
    }
    return render(request, 'core/home.html', context)


def offline(request):
    """Fallback کوچک و مستقل PWA هنگامی که navigation بدون اینترنت انجام شود."""
    response = render(request, 'offline.html', status=200)
    response['Cache-Control'] = 'public, max-age=300'
    return response


def service_worker(request):
    """Service worker در ریشهٔ origin ارائه می‌شود تا scope آن کل فروشگاه باشد.

    URL فایل عمداً static نیست: مرورگر برای گسترده‌تر شدن scope از دایرکتوری
    اسکریپت به هدر Service-Worker-Allowed نیاز دارد.
    """
    response = render(request, 'service-worker.js', content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


# ---------------------------------------------------------------- brand assets

logger = logging.getLogger(__name__)

_ICON_CACHE_SECONDS = 60 * 60 * 24 * 30


def _cache_brand_asset(response, request, brand):
    """Versioned brand URLs never change content; anything else revalidates soon."""
    if request.GET.get('v') == brand.version:
        response['Cache-Control'] = 'public, max-age=31536000, immutable'
    else:
        response['Cache-Control'] = 'public, max-age=300'
    return response


@require_safe
def web_manifest(request):
    """manifest نصب اپ (PWA) با نام و آیکن فعلی؛ قبلاً یک فایل JSON ثابت بود."""
    brand = branding.get_brand(request)
    response = JsonResponse(
        branding.manifest_data(brand),
        json_dumps_params={'ensure_ascii': False, 'indent': 2},
        content_type='application/manifest+json; charset=utf-8',
    )
    return _cache_brand_asset(response, request, brand)


@require_safe
def brand_icon(request, size):
    """آیکن مربعی PNG ساخته‌شده از فاوآیکن (یا لوگوی) آپلودشده در «تنظیمات سایت»."""
    if size not in branding.ICON_SIZES:
        raise Http404('اندازهٔ آیکن پشتیبانی نمی‌شود.')
    brand = branding.get_brand(request)
    if not brand.has_custom_icon:
        return redirect(static(branding.DEFAULT_ICONS[size]))
    # The key contains the brand version, so a new upload can never be answered
    # with an old icon, even by a per-process cache in another worker.
    cache_key = f'fm:brand-icon:{brand.version}:{size}'
    payload = cache.get(cache_key)
    if payload is None:
        try:
            payload = branding.render_square_icon(brand.icon_source, size)
        except branding.ICON_ERRORS as exc:
            logger.warning('Brand icon %s could not be rendered from %s: %s', size, brand.icon_source.name, exc)
            return redirect(static(branding.DEFAULT_ICONS[size]))
        cache.set(cache_key, payload, _ICON_CACHE_SECONDS)
    response = HttpResponse(payload, content_type='image/png')
    return _cache_brand_asset(response, request, brand)


@require_safe
def favicon(request):
    """``/favicon.ico`` که مرورگرها خودکار درخواست می‌کنند → آیکن فعلی سایت.

    عمداً موقت (۳۰۲) است: ریدایرکت دائمی (۳۰۱) قبلی برای همیشه در مرورگر کش
    می‌شد و آیکن تب هرگز قابل تغییر نبود.
    """
    response = redirect(branding.get_brand(request).favicon_ico_url)
    response['Cache-Control'] = 'no-cache'
    return response


def contact(request):
    if request.method == 'POST':
        form = ContactUsForm(request.POST)
        # The contact form is public and unauthenticated: without a limit a
        # script can fill the staff inbox and the database with junk messages.
        throttle = get_throttle('contact')
        identity = form.data.get('email', '')
        if throttle.is_throttled(request, identity):
            throttle.record(request, identity)
            messages.error(request, 'تعداد پیام‌های ارسالی شما زیاد است. لطفاً کمی بعد دوباره تلاش کنید.')
            return render(request, 'core/contact.html', {'form': form}, status=429)

        if form.is_valid():
            throttle.record(request, identity)
            form.save()
            messages.success(request, 'پیام شما با موفقیت ثبت شد. تیم پشتیبانی در اولین فرصت با شما تماس می‌گیرد.')
            return redirect('core:contact')
    else:
        form = ContactUsForm()

    return render(request, 'core/contact.html', {'form': form})


def about(request):
    return render(request, 'core/about.html')


def llms_txt(request):
    """راهنمای محتوا برای مدل‌های زبانی (استاندارد llmstxt.org).

    خلاصه‌ای ساخت‌یافته از سایت به‌صورت مارک‌داون تا دستیارهای هوش مصنوعی
    بتوانند محتوا، محصولات و سیاست‌های سایت را دقیق درک و ارجاع دهند.
    همهٔ لینک‌ها مطلق‌اند تا خزندهٔ هوش مصنوعی بدون دانستن دامنه بتواند
    از آن‌ها استفاده کند؛ دسته‌هایی که محتوای منتشرشده ندارند فهرست
    نمی‌شوند تا فایل، نقشهٔ واقعی و به‌روز سایت بماند.
    """
    from blog.models import Category as BlogCategory
    from product.models import ProductCategory

    context = {
        # build_absolute_uri('/') انتهایش اسلش دارد؛ بدون اسلش نگه می‌داریم
        # تا در قالب به‌صورت «{{ site_base }}/products/» استفاده شود.
        'site_base': request.build_absolute_uri('/')[:-1],
        'top_products': Product.objects.filter(status='published')
            .order_by('-sales_count', '-views')[:15],
        'latest_articles': Article.objects.filter(status='published')
            .order_by('-created_at')[:10],
        'packages': ServicePackage.objects.filter(is_active=True),
        'product_categories': ProductCategory.objects.annotate(
            published_count=models.Count(
                'categories', filter=models.Q(categories__status='published'),
            ),
        ).filter(published_count__gt=0).order_by('title'),
        'blog_categories': BlogCategory.objects.annotate(
            published_count=models.Count(
                'articles', filter=models.Q(articles__status='published'),
            ),
        ).filter(published_count__gt=0).order_by('title'),
    }
    return render(request, 'core/llms.txt', context, content_type='text/plain; charset=utf-8')


# ------------------------------------------------ هندلر خطاها (با قالب اختصاصی و noindex)

def custom_400(request, exception=None):
    return render(request, 'errors/400.html', status=400)


def custom_403(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def custom_404(request, exception=None):
    return render(request, 'errors/404.html', status=404)


#: صفحه جایگزین وقتی حتی رندر قالب ۵۰۰ هم شکست می‌خورد (مثلاً دیتابیس در دسترس نیست).
_FALLBACK_500 = """<!DOCTYPE html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, follow"><title>خطای سرور</title>
<script>try{if(localStorage.getItem('fm-theme')==='dark'){document.documentElement.setAttribute('data-theme','dark')}}catch(e){}</script>
<style>body{font-family:Tahoma,Arial,sans-serif;background:#f6f8fa;color:#22333f;
display:grid;place-items:center;min-height:100vh;margin:0;text-align:center;padding:24px}
h1{font-size:22px;margin:0 0 12px}p{color:#5d7285;line-height:2;margin:0 0 20px}
a{display:inline-block;background:#2d6e74;color:#fff;text-decoration:none;
padding:11px 28px;border-radius:999px;font-weight:bold}
[data-theme=dark]{color-scheme:dark}[data-theme=dark] body{background:#0f1720;color:#e8eef4}
[data-theme=dark] p{color:#9db0c0}</style></head>
<body><div><h1>خطایی در سرور رخ داد</h1>
<p>مشکل از سمت ماست و تیم فنی در جریان قرار گرفت.<br>لطفاً چند دقیقه بعد دوباره تلاش کنید.</p>
<a href="/">بازگشت به صفحه اصلی</a></div></body></html>"""


def custom_500(request):
    """صفحه خطای ۵۰۰.

    قالب از base.html ارث می‌برد و base به context processorهایی وابسته است که
    به دیتابیس می‌زنند. اگر همان دیتابیس عامل خطا باشد، رندر قالب هم می‌شکند و
    کاربر صفحه سفید می‌بیند؛ بنابراین یک نسخه ساده و بی‌وابستگی هم داریم.
    """
    try:
        return render(request, 'errors/500.html', status=500)
    except Exception:
        return HttpResponse(_FALLBACK_500, status=500, content_type='text/html; charset=utf-8')


def newsletter_subscribe(request):
    """عضویت در خبرنامه (AJAX) — با CSRF و اعتبارسنجی ایمیل."""
    from django.http import JsonResponse
    from django.views.decorators.http import require_POST

    @require_POST
    def _subscribe(request):
        import json as _json
        from .models import NewsletterSubscriber
        try:
            data = _json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({'ok': False, 'message': 'درخواست نامعتبر است.'}, status=400)
        # Valid JSON that is not an object, or a non-string email, used to raise
        # AttributeError -> HTTP 500.
        if not isinstance(data, dict):
            return JsonResponse({'ok': False, 'message': 'درخواست نامعتبر است.'}, status=400)
        email = data.get('email')
        email = email.strip().lower() if isinstance(email, str) else ''
        from django.core.validators import EmailValidator
        from django.core.exceptions import ValidationError
        try:
            EmailValidator()(email)
        except ValidationError:
            return JsonResponse({'ok': False, 'message': 'ایمیل واردشده معتبر نیست.'})
        throttle = get_throttle('newsletter')
        if throttle.is_throttled(request, email):
            throttle.record(request, email)
            return JsonResponse(
                {'ok': False, 'message': 'تعداد درخواست‌های شما زیاد است. کمی بعد دوباره تلاش کنید.'},
                status=429,
            )
        throttle.record(request, email)
        subscriber, created = NewsletterSubscriber.objects.get_or_create(email=email, defaults={'is_active': True})
        if created:
            return JsonResponse({'ok': True, 'message': 'عضویت شما در خبرنامه با موفقیت ثبت شد؛ تخفیف‌ها و فایل‌های جدید را زودتر از همه دریافت می‌کنید.'})
        if not subscriber.is_active:
            # عضویت قبلاً غیرفعال شده بود (مثلاً توسط مدیر)؛ پیام «قبلاً ثبت
            # شده‌اید» بدون فعال‌سازی دوباره یعنی کاربر فکر می‌کند عضو است
            # ولی هیچ ایمیلی نمی‌گیرد — پس عضویتش را واقعاً برمی‌گردانیم.
            subscriber.is_active = True
            subscriber.save(update_fields=['is_active'])
            return JsonResponse({'ok': True, 'message': 'عضویت شما در خبرنامه دوباره فعال شد؛ تخفیف‌ها و فایل‌های جدید را زودتر از همه دریافت می‌کنید.'})
        return JsonResponse({'ok': True, 'message': 'این ایمیل قبلاً در خبرنامه ثبت شده است.'})

    return _subscribe(request)
