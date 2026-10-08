import json
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.core.paginator import Paginator
from django.db.models import Min, Max
from urllib.parse import urlencode
from django.http import JsonResponse, FileResponse, Http404

from .models import Product, ProductComment, ProductCategory, ProductBrand, PRODUCT_TYPES
from downloads.models import DownloadToken
from dashboard.models import Wishlist
from cart.models import Order, OrderItem
from core.models import SiteSettings


def _products_per_page():
    """تعداد محصول در هر صفحه؛ از تنظیمات سایت قابل تغییر است."""
    settings_row = SiteSettings.objects.first()
    return settings_row.products_per_page if settings_row and settings_row.products_per_page else 9


def redirect_to_home(request):
    """هدایت مسیرهای خالی (بدون نامک) به صفحه مرتبط، نه صفحه اصلی."""
    path = request.path
    if path.startswith('/blog'):
        return redirect('blog:article_list')
    return redirect('product:product_list')


def get_pages_to_show(current_page, total_pages):
    if total_pages <= 3:
        return list(range(1, total_pages + 1))

    if current_page <= 2:
        return [1, 2, 3, '...', total_pages]

    if current_page >= total_pages - 1:
        return [1, '...', total_pages - 2, total_pages - 1, total_pages]

    return [1, '...', current_page - 1, current_page, current_page + 1, '...', total_pages]


def _positive_decimal(value):
    """Return a non-negative decimal filter value or ``None`` for malformed input."""
    if value in (None, ''):
        return None
    try:
        parsed = Decimal(str(value).replace(',', '').strip())
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _apply_digital_filters(request, products):
    """فیلترهای مخصوص محصولات دیجیتال: قیمت، نوع محصول، سازنده و دانلود آنی.

    Query strings are user input: invalid prices and brand ids must be ignored,
    rather than causing a database conversion error or a 500 response.
    """
    min_price = _positive_decimal(request.GET.get('min_price'))
    max_price = _positive_decimal(request.GET.get('max_price'))
    selected_types = [value for value in request.GET.getlist('type') if value in dict(PRODUCT_TYPES)]
    selected_brands = [value for value in request.GET.getlist('brand') if value.isdigit()]
    instant_only = request.GET.get('instant')

    if min_price is not None:
        products = products.filter(price__gte=min_price)
    if max_price is not None:
        products = products.filter(price__lte=max_price)
    if min_price is not None and max_price is not None and min_price > max_price:
        # An inverted range cannot match anything but should remain a valid request.
        products = products.none()

    if selected_types:
        products = products.filter(product_type__in=selected_types)

    if selected_brands:
        products = products.filter(brand__id__in=[int(value) for value in selected_brands])

    if instant_only == '1':
        products = products.filter(is_unlimited=True)

    return products.distinct(), selected_types, selected_brands, instant_only


def _price_range(qs):
    return qs.aggregate(min=Min('price'), max=Max('price'))


def _product_cards(queryset):
    """Fetch the relations shown by reusable product-card templates in bulk."""
    return queryset.select_related('digital_asset').prefetch_related('brand')


def _paginate(request, products, per_page=None):
    paginator = Paginator(products, per_page or _products_per_page())
    page_number = request.GET.get('page')
    object_list = paginator.get_page(page_number)
    pages_to_show = get_pages_to_show(object_list.number, paginator.num_pages)
    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    return object_list, pages_to_show, urlencode(query_params)


def _snapshot_contains_product(items_data, product_id):
    """Match an old order snapshot by product id, never by a title substring."""
    raw_items = items_data.get('items', []) if isinstance(items_data, dict) else items_data
    if not isinstance(raw_items, list):
        return False
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        item_product_id = item.get('product_id', item.get('product'))
        if str(item_product_id) == str(product_id):
            return True
    return False


def _has_purchased_product(user, product):
    paid_statuses = ['paid', 'processing', 'shipped', 'delivered']
    if OrderItem.objects.filter(
        order__user=user,
        order__status__in=paid_statuses,
        product=product,
    ).exists():
        return True

    # Orders created before OrderItem existed still have their immutable JSON
    # snapshot.  Keep those customers recognised without false positives from
    # similar product titles.
    legacy_snapshots = Order.objects.filter(
        user=user,
        status__in=paid_statuses,
    ).values_list('items_data', flat=True)
    return any(_snapshot_contains_product(snapshot, product.pk) for snapshot in legacy_snapshots)


def product_list(request):
    published = Product.objects.filter(status='published')
    products = _product_cards(published.order_by('-created_at'))

    products, selected_types, selected_brands, instant_only = _apply_digital_filters(request, products)
    prices = _price_range(published)
    object_list, pages_to_show, querystring = _paginate(request, products)

    context = {
        'products': object_list,
        'brands': ProductBrand.objects.all(),
        'product_types': PRODUCT_TYPES,
        'selected_types': selected_types,
        'selected_brands': [int(b) for b in selected_brands if b.isdigit()],
        'pages_to_show': pages_to_show,
        'min_price': request.GET.get('min_price') or prices['min'],
        'max_price': request.GET.get('max_price') or prices['max'],
        'actual_min_price': prices['min'],
        'actual_max_price': prices['max'],
        'instant_only': instant_only,
        'querystring': querystring,
    }
    return render(request, 'product/product_list.html', context)


def category_product_list(request, slug):
    category = get_object_or_404(ProductCategory, slug=slug)
    published = Product.objects.filter(status='published')
    products = _product_cards(published.filter(category=category))

    products, selected_types, selected_brands, instant_only = _apply_digital_filters(request, products)
    prices = _price_range(published.filter(category=category))
    if prices['min'] is None:
        prices = _price_range(published)
    object_list, pages_to_show, querystring = _paginate(request, products)

    context = {
        'category': category,
        'products': object_list,
        'brands': ProductBrand.objects.all(),
        'product_types': PRODUCT_TYPES,
        'selected_types': selected_types,
        'selected_brands': [int(b) for b in selected_brands if b.isdigit()],
        'pages_to_show': pages_to_show,
        'min_price': request.GET.get('min_price') or prices['min'],
        'max_price': request.GET.get('max_price') or prices['max'],
        'actual_min_price': prices['min'],
        'actual_max_price': prices['max'],
        'instant_only': instant_only,
        'querystring': querystring,
    }
    return render(request, 'product/category_product_list.html', context)


def brand_product_list(request, slug):
    brand = get_object_or_404(ProductBrand, slug=slug)
    published = Product.objects.filter(status='published')
    products = _product_cards(published.filter(brand=brand))

    products, selected_types, selected_brands, instant_only = _apply_digital_filters(request, products)
    prices = _price_range(published)
    object_list, pages_to_show, querystring = _paginate(request, products)

    context = {
        'brand': brand,
        'brands': ProductBrand.objects.all().order_by('-views')[:6],
        'products': object_list,
        'product_types': PRODUCT_TYPES,
        'selected_types': selected_types,
        'pages_to_show': pages_to_show,
        'min_price': request.GET.get('min_price') or prices['min'],
        'max_price': request.GET.get('max_price') or prices['max'],
        'actual_min_price': prices['min'],
        'actual_max_price': prices['max'],
        'instant_only': instant_only,
        'querystring': querystring,
    }
    return render(request, 'product/brand_product_list.html', context)


def discount_product_list(request):
    published = Product.objects.filter(status='published')
    products = _product_cards(
        published.filter(
            old_price__isnull=False,
            old_price__gt=models.F('price')
        ).annotate(
            discount=models.ExpressionWrapper(
                (models.F('old_price') - models.F('price')) * 100 / models.F('old_price'),
                output_field=models.IntegerField())
        ).filter(discount__gt=0).order_by('-discount')
    )

    products, selected_types, selected_brands, instant_only = _apply_digital_filters(request, products)
    prices = _price_range(published)
    object_list, pages_to_show, querystring = _paginate(request, products)

    context = {
        'products': object_list,
        'product_types': PRODUCT_TYPES,
        'selected_types': selected_types,
        'pages_to_show': pages_to_show,
        'min_price': request.GET.get('min_price') or prices['min'],
        'max_price': request.GET.get('max_price') or prices['max'],
        'actual_min_price': prices['min'],
        'actual_max_price': prices['max'],
        'instant_only': instant_only,
        'querystring': querystring,
    }
    return render(request, 'product/discount_product_list.html', context)


def product_search(request):
    products_search = request.GET.get('search', '')
    products = _product_cards(
        Product.objects.filter(title__icontains=products_search, status='published')
        .order_by('-created_at')
        .prefetch_related('category')
    )

    # جست‌وجوی زنده (AJAX) — فقط نتایج محدود با JSON
    if request.GET.get('ajax') and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        results = []
        for p in products[:6]:
            # ``category.all()`` consumes the prefetch cache; ``first()`` did
            # not consistently do so across supported Django releases.
            cat = next(iter(p.category.all()), None)
            results.append({
                'title': p.title,
                'url': f'/products/{p.pid}/{p.slug}/',
                'price': p.price,
                'image': p.image.url if p.image else None,
                'category': cat.title if cat else '',
            })
        from django.http import JsonResponse
        return JsonResponse({'results': results, 'count': products.count()})

    products, selected_types, selected_brands, instant_only = _apply_digital_filters(request, products)
    prices = _price_range(Product.objects.filter(status='published'))
    object_list, pages_to_show, querystring = _paginate(request, products)

    context = {
        'products': object_list,
        'product_types': PRODUCT_TYPES,
        'selected_types': selected_types,
        'pages_to_show': pages_to_show,
        'search': products_search,
        'min_price': request.GET.get('min_price') or prices['min'],
        'max_price': request.GET.get('max_price') or prices['max'],
        'actual_min_price': prices['min'],
        'actual_max_price': prices['max'],
        'instant_only': instant_only,
        'querystring': querystring,
    }
    return render(request, 'product/product_list.html', context)


def product_detail(request, pid, slug):
    # Draft products must be reachable only from Django admin, not through a
    # guessed pid/slug URL.
    products = get_object_or_404(
        Product.objects.select_related('digital_asset').prefetch_related(
            'product_images', 'category', 'brand'
        ),
        pid=pid,
        slug=slug,
        status='published',
    )
    product_image = products.product_images.all()

    if request.method == 'POST' and request.headers.get('Content-Type', '').startswith('application/json'):
        try:
            data = json.loads(request.body or '{}')
        except (TypeError, ValueError, json.JSONDecodeError):
            return JsonResponse({'status': 'fail', 'message': 'درخواست دیدگاه نامعتبر است.'}, status=400)
        body = (data.get('body') or '').strip()
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'fail', 'message': 'برای ثبت دیدگاه وارد حساب شوید.'}, status=403)
        if not body:
            return JsonResponse({'status': 'fail', 'message': 'متن دیدگاه را وارد کنید.'}, status=400)
        if len(body) > 2000:
            return JsonResponse({'status': 'fail', 'message': 'متن دیدگاه بیش از حد طولانی است.'}, status=400)
        comment = ProductComment.objects.create(body=body, product=products, author=request.user)
        return JsonResponse({'status': 'success', 'comment_id': comment.id})

    comments = products.product_comments.filter(status='published').select_related(
        'author', 'author__profile'
    ).order_by('-created_at')

    viewed_products = request.session.get('viewed_products', [])
    if products.id not in viewed_products:
        products.views += 1
        products.save(update_fields=['views'])
        viewed_products.append(products.id)
        request.session['viewed_products'] = viewed_products

    is_in_wishlist = False
    user_tokens = []
    already_purchased = False
    in_cart = False
    if request.user.is_authenticated:
        is_in_wishlist = Wishlist.objects.filter(user=request.user, product=products).exists()
        user_tokens = list(DownloadToken.objects.filter(user=request.user, product=products).order_by('-created_at'))
        already_purchased = _has_purchased_product(request.user, products)
        in_cart = products.cartitem_set.filter(cart__user=request.user).exists()

    context = {
        'products': products,
        'product_image': product_image,
        'comments': comments,
        'is_in_wishlist': is_in_wishlist,
        'user_tokens': user_tokens,
        'already_purchased': already_purchased,
        'in_cart': in_cart,
    }
    return render(request, 'product/product_detail.html', context)


@login_required
def download_asset(request, pid):
    """دانلود فایل دیجیتال برای خریدار تأییدشده (از طریق توکن دانلود)."""
    product = get_object_or_404(Product.objects.select_related('digital_asset'), pid=pid)
    asset = getattr(product, 'digital_asset', None)
    if asset is None:
        raise Http404('فایلی برای این محصول ثبت نشده است.')

    token = DownloadToken.objects.filter(user=request.user, product=product).order_by('-created_at').first()
    if token is None or not token.is_valid:
        messages.error(request, 'شما به این فایل دسترسی ندارید یا لینک دانلود شما منقضی شده است.')
        return redirect('product:product_detail', pid=product.pid, slug=product.slug)

    # ``register_download`` rechecks validity in one conditional database
    # update, preventing concurrent requests from exceeding the token limit.
    if not token.register_download():
        messages.error(request, 'لینک دانلود شما منقضی شده یا به سقف تعداد دانلود رسیده است.')
        return redirect('product:product_detail', pid=product.pid, slug=product.slug)

    type(asset).objects.filter(pk=asset.pk).update(download_count=models.F('download_count') + 1)
    return FileResponse(asset.file.open('rb'), as_attachment=True, filename=asset.file.name.rsplit('/', 1)[-1])
