import json

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
from cart.models import Order


def redirect_to_home(request):
    return redirect('core:home')


def get_pages_to_show(current_page, total_pages):
    if total_pages <= 3:
        return list(range(1, total_pages + 1))

    if current_page <= 2:
        return [1, 2, 3, '...', total_pages]

    if current_page >= total_pages - 1:
        return [1, '...', total_pages - 2, total_pages - 1, total_pages]

    return [1, '...', current_page - 1, current_page, current_page + 1, '...', total_pages]


def _apply_digital_filters(request, products):
    """فیلترهای مخصوص محصولات دیجیتال: قیمت، نوع محصول، سازنده و دانلود آنی."""
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    selected_types = request.GET.getlist('type')
    selected_brands = request.GET.getlist('brand')
    instant_only = request.GET.get('instant')

    if min_price and max_price:
        products = products.filter(price__gte=min_price, price__lte=max_price)

    if selected_types:
        products = products.filter(product_type__in=selected_types)

    if selected_brands:
        products = products.filter(brand__id__in=selected_brands)

    if instant_only == '1':
        products = products.filter(is_unlimited=True)

    return products.distinct(), selected_types, selected_brands, instant_only


def _price_range(qs):
    return qs.aggregate(min=Min('price'), max=Max('price'))


def _paginate(request, products, per_page=9):
    paginator = Paginator(products, per_page)
    page_number = request.GET.get('page')
    object_list = paginator.get_page(page_number)
    pages_to_show = get_pages_to_show(object_list.number, paginator.num_pages)
    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    return object_list, pages_to_show, urlencode(query_params)


def product_list(request):
    published = Product.objects.filter(status='published')
    products = published.order_by('-created_at')

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
    products = published.filter(category=category)

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
    products = published.filter(brand=brand)

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
    products = published.filter(
        old_price__isnull=False,
        old_price__gt=models.F('price')
    ).annotate(
        discount=models.ExpressionWrapper(
            (models.F('old_price') - models.F('price')) * 100 / models.F('old_price'),
            output_field=models.IntegerField())).filter(discount__gt=0).order_by('-discount')

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
    products = Product.objects.filter(title__icontains=products_search, status='published').order_by('-created_at')

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
    products = get_object_or_404(Product.objects.prefetch_related('product_images'), pid=pid, slug=slug)
    product_image = products.product_images.all()

    if request.method == 'POST' and request.headers.get('Content-Type') == 'application/json':
        data = json.loads(request.body)
        body = data.get('body')
        if request.user.is_authenticated and body:
            comment = ProductComment.objects.create(body=body, product=products, author=request.user)
            return JsonResponse({'status': 'success', 'comment_id': comment.id})
        return JsonResponse({'status': 'fail'}, status=400)

    comments = products.product_comments.filter(status='published').order_by('-created_at')

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
        already_purchased = Order.objects.filter(
            user=request.user, status__in=['paid', 'processing', 'shipped', 'delivered'],
            items_data__icontains=products.title,
        ).exists()
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

    asset.download_count = models.F('download_count') + 1
    asset.save(update_fields=['download_count'])
    token.register_download()
    return FileResponse(asset.file.open('rb'), as_attachment=True, filename=asset.file.name.rsplit('/', 1)[-1])
