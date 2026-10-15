from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .coupons import discount_amount, release_coupon_reservation, revalidate_coupon
from .models import Cart, CartItem, Coupon, Order
from product.models import Product
from django.db import transaction as db_transaction
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from core.decorators import login_required_json


def _cart_summary(user, revalidate=False):
    """جمع سبد خرید دیجیتال (بدون هزینه ارسال).

    With ``revalidate`` the applied coupon is re-checked *before* the totals
    are computed; computing them first showed a stale payable amount next to
    an already-corrected discount on the first view after a coupon lapsed.
    """
    cart = Cart.objects.filter(user=user).select_related('coupon').first()
    items = list(cart.items.select_related('product')) if cart else []
    if revalidate:
        revalidate_coupon(cart, items)
    total_price = sum(item.total_price for item in items)
    coupon_discount = cart.coupon_discount if cart else 0
    # A product can be unpublished or run out of licences after it was added;
    # the cart flags it instead of failing later at the gateway step.
    unavailable = [item for item in items
                   if item.product.status != 'published' or not item.product.is_available]
    product_savings = sum(
        (item.product.old_price - item.product.price) * item.quantity
        for item in items
        if item.product.old_price and item.product.old_price > item.product.price
    )
    return {
        'cart': cart,
        'cart_items': items,
        'total_price': total_price,
        'coupon_discount': coupon_discount,
        'final_price': max(0, total_price - coupon_discount),
        'unavailable_items': unavailable,
        'product_savings': product_savings,
    }


@login_required
def cart(request):
    # محتویات سبد می‌تواند از آخرین باری که تخفیف اعمال شده تغییر کرده باشد
    # (مثلاً حذف آیتم در یک تب دیگر)؛ تخفیف را دوباره با جمع فعلی بسنجیم.
    summary = _cart_summary(request.user, revalidate=True)

    from product.models import Product as _Product

    in_cart = [item.product_id for item in summary['cart_items']]
    suggestions = []
    if summary['cart_items']:
        # ``Product.category`` is a many-to-many field.
        category_ids = _Product.category.through.objects.filter(product_id__in=in_cart).values('productcategory_id')
        suggestions = list(
            _Product.objects.filter(status='published', category__in=category_ids)
            .exclude(pk__in=in_cart).distinct().order_by('-sales_count', '-created_at')[:4]
        )
    context = {
        'cart': summary['cart'],
        'cart_items': summary['cart_items'],
        'total_price': summary['total_price'],
        'final_price': summary['final_price'],
        'coupon_discount': summary['coupon_discount'],
        'unavailable_items': summary['unavailable_items'],
        'product_savings': summary['product_savings'],
        'suggestions': suggestions,
    }
    return render(request, 'cart/cart.html', context)


@login_required_json
@never_cache
def cart_drawer(request):
    """The cart drawer fragment, re-fetched by the storefront after an AJAX add.

    The drawer is rendered with the page (``includes/cart_drawer.html``, fed by
    the ``shop_func`` context processor).  Without a refresh it still said
    "your cart is empty" right after the "added to cart" message.
    """
    return render(request, 'includes/cart_drawer.html')


@login_required_json
@require_POST
def add_to_cart(request, product_id):
    product = Product.objects.filter(pk=product_id, status='published').first()
    if product is None:
        return JsonResponse({'success': False, 'message': 'این فایل دیگر در فروشگاه موجود نیست.'}, status=404)
    if not product.is_available:
        return JsonResponse({'success': False, 'message': 'این فایل در حال حاضر قابل خرید نیست.'}, status=400)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    # محصولات دیجیتال کمّیت ندارند؛ هر فایل فقط یک‌بار به سبد اضافه می‌شود.
    _, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': 1})
    count = cart.items.count()
    if not created:
        # Not an error for the customer: the file *is* in the cart (a double
        # click, or a second tab).  Report it as such so the UI can open the
        # drawer instead of showing a red error.
        return JsonResponse({
            'success': True,
            'already_in_cart': True,
            'message': 'این فایل از قبل در سبد خرید شما موجود است.',
            'cart_count': count,
        })

    return JsonResponse({
        'success': True,
        'message': 'فایل با موفقیت به سبد خرید اضافه شد.',
        'cart_count': count,
    })


@login_required_json
@require_POST
def remove_cart_item(request, item_id):
    cart_item = CartItem.objects.filter(pk=item_id, cart__user=request.user).select_related('cart').first()
    if cart_item is None:
        # Already removed (another tab, double click): the desired state holds.
        cart = Cart.objects.filter(user=request.user).first()
        remaining_items = list(cart.items.select_related('product')) if cart else []
        return JsonResponse({
            'success': True,
            'already_removed': True,
            'total_price': sum(item.total_price for item in remaining_items),
            'final_price': cart.final_price if cart else 0,
            'cart_count': len(remaining_items),
        })
    cart = cart_item.cart
    cart_item.delete()

    # تخفیف باید نسبت به جمع جدید سبد دوباره محاسبه شود؛ در غیر این صورت
    # حذف آیتم گران‌قیمت، مبلغ قابل پرداخت را به صفر می‌رساند.
    remaining_items = list(cart.items.select_related('product'))
    revalidate_coupon(cart, remaining_items)

    return JsonResponse({
        'success': True,
        'total_price': sum(item.total_price for item in remaining_items),
        'final_price': cart.final_price,
        'cart_count': len(remaining_items),
    })


def _paid_coupon_uses(user, coupon):
    """Count completed uses for the per-customer coupon limit.

    Coupon details live in the immutable order snapshot, so this works for old
    orders as well and does not rely on a mutable cart.
    """
    snapshots = Order.objects.filter(user=user, status='paid').values_list('items_data', flat=True)
    coupon_code = coupon.code.casefold()
    return sum(
        1
        for snapshot in snapshots
        if isinstance(snapshot, dict)
        and str(snapshot.get('coupon') or '').casefold() == coupon_code
    )


@login_required
@require_POST
def apply_coupon(request):
    coupon_code = (request.POST.get('coupon_code') or '').strip()
    try:
        # Lock both rows while checking capacity and reserving the code.  This
        # prevents two parallel tabs from consuming the final allowed use.
        with db_transaction.atomic():
            cart = Cart.objects.select_for_update().get(user=request.user)
            if not cart.items.exists():
                messages.error(request, 'سبد خرید شما خالی است')
                return redirect('cart:cart')

            # Codes are matched case-insensitively.  Prefer an exact-case match;
            # an ambiguous code (legacy case-variant duplicates) is refused
            # instead of raising MultipleObjectsReturned.
            matches = list(Coupon.objects.select_for_update().filter(code__iexact=coupon_code))
            coupon = next((c for c in matches if c.code == coupon_code), None)
            if coupon is None and len(matches) == 1:
                coupon = matches[0]
            if coupon is None:
                raise Coupon.DoesNotExist
            if cart.coupon:
                messages.warning(request, 'یک کد تخفیف قبلاً اعمال شده است')
                return redirect('cart:cart')

            if not coupon.is_valid():
                messages.error(request, 'کد تخفیف معتبر نیست یا منقضی شده است')
                return redirect('cart:cart')

            if coupon.per_user_limit and _paid_coupon_uses(request.user, coupon) >= coupon.per_user_limit:
                messages.error(request, 'سقف استفاده شما از این کد تخفیف تکمیل شده است.')
                return redirect('cart:cart')

            total_price = sum(item.total_price for item in cart.items.select_related('product'))
            if coupon.minimum_order_amount and total_price < coupon.minimum_order_amount:
                messages.error(request, f'حداقل مبلغ سفارش برای این کد تخفیف {coupon.minimum_order_amount:,} تومان است')
                return redirect('cart:cart')

            discount = discount_amount(coupon, total_price)

            cart.coupon = coupon
            cart.coupon_discount = discount
            cart.save(update_fields=['coupon', 'coupon_discount', 'updated_at'])

            # Applying a coupon reserves one of its global uses.  This keeps a
            # final-use coupon from being granted simultaneously in two carts.
            # A full coupon is *not* deactivated: ``is_valid`` already refuses
            # new reservations, while deactivating made every cart that held
            # a counted reservation lose its discount on the next revalidation
            # and kept released uses unclaimable for good.
            coupon.usage_count += 1
            coupon.save(update_fields=['usage_count'])

        messages.success(request, f'کد تخفیف {coupon.code} با موفقیت اعمال شد ({discount:,} تومان تخفیف)')
    except Coupon.DoesNotExist:
        messages.error(request, 'کد تخفیف وارد شده معتبر نیست')
    return redirect('cart:cart')


@login_required
def shopping_payment(request):
    # The payment page is reachable without opening the cart, so an expired or
    # staff-disabled coupon must be re-checked here before a total is shown.
    summary = _cart_summary(request.user, revalidate=True)
    if not summary['cart_items']:
        messages.warning(request, 'سبد خرید شما خالی است')
        return redirect('cart:cart')

    from notifications.sms import normalize_mobile
    from payments.models import GatewaySettings
    from payments.services import GATEWAYS, MOBILE_REQUIRED_KEYS

    # درگاهِ پیاده‌سازی‌نشده هرگز به مشتری پیشنهاد نمی‌شود؛ درگاهِ فعالِ
    # پیکربندی‌نشده در شروع پرداخت با پیام روشن رد می‌شود و اینجا می‌ماند تا
    # مدیر متوجه ناقص‌بودن تنظیمات شود. چنین درگاهی (و درگاه اقساطی‌ای که برای
    # این مبلغ طرح ندارد) برای مشتری غیرقابل‌انتخاب نمایش داده می‌شود تا کسی
    # روی گزینه‌ای که پرداخت را شروع نمی‌کند کلیک نکند.
    gateways = [gateway for gateway in GatewaySettings.objects.filter(is_enabled=True) if gateway.is_implemented]
    for gateway in gateways:
        gateway.needs_mobile = gateway.key in MOBILE_REQUIRED_KEYS
        gateway.eligible, gateway.offer_title, gateway.offer_description = True, '', ''
        adapter = GATEWAYS.get(gateway.key)
        if gateway.is_configured and hasattr(adapter, 'eligibility') and gateway.key == 'snappay':
            # اسنپ‌پی برای هر مبلغ، شرایط اقساط (مثلاً «۴ قسط بدون بهره») را برمی‌گرداند.
            gateway.eligible, gateway.offer_title, gateway.offer_description = adapter.eligibility(summary['final_price'])
        gateway.selectable = gateway.is_configured and gateway.eligible
    selectable = [gateway for gateway in gateways if gateway.selectable]
    misconfigured = [gateway for gateway in gateways if not gateway.is_configured] if request.user.is_staff else []
    profile = getattr(request.user, 'profile', None)
    context = {
        'cart': summary['cart'],
        'cart_items': summary['cart_items'],
        'total_price': summary['total_price'],
        'final_price': summary['final_price'],
        'unavailable_items': summary['unavailable_items'],
        'enabled_gateways': gateways,
        'default_gateway': selectable[0].key if selectable else '',
        'misconfigured_gateways': misconfigured,
        'has_installment_gateway': any(g.is_installment for g in selectable),
        'customer_mobile': normalize_mobile(getattr(profile, 'phone', '') or ''),
    }
    return render(request, 'cart/shopping_payment.html', context)


@login_required
def successful_payment(request):
    messages.info(request, 'برای ثبت سفارش، ابتدا از یکی از درگاه‌های پرداخت استفاده کنید.')
    return redirect('cart:shopping_payment')


@login_required
@require_POST
def remove_coupon(request):
    """Detach the applied coupon so the customer can switch codes or pay full price.

    Without this, a cart that once had a coupon could never use a different one:
    ``apply_coupon`` refuses while a coupon is attached, and the only escape was
    emptying the whole cart.
    """
    cart = Cart.objects.filter(user=request.user).first()
    if cart is None or cart.coupon is None:
        messages.info(request, 'هیچ کد تخفیفی روی سبد شما اعمال نشده است.')
        return redirect('cart:cart')

    release_coupon_reservation(cart.coupon)
    cart.coupon = None
    cart.coupon_discount = 0
    cart.save(update_fields=['coupon', 'coupon_discount', 'updated_at'])
    messages.success(request, 'کد تخفیف از سبد خرید حذف شد.')
    return redirect('cart:cart')
