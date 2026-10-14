from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .coupons import discount_amount, release_coupon_reservation, revalidate_coupon
from .models import Cart, CartItem, Coupon, Order
from product.models import Product
from django.db import transaction as db_transaction
from django.views.decorators.http import require_POST


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
    return {
        'cart': cart,
        'cart_items': items,
        'total_price': total_price,
        'coupon_discount': coupon_discount,
        'final_price': max(0, total_price - coupon_discount),
    }


@login_required
def cart(request):
    # محتویات سبد می‌تواند از آخرین باری که تخفیف اعمال شده تغییر کرده باشد
    # (مثلاً حذف آیتم در یک تب دیگر)؛ تخفیف را دوباره با جمع فعلی بسنجیم.
    summary = _cart_summary(request.user, revalidate=True)

    context = {
        'cart': summary['cart'],
        'cart_items': summary['cart_items'],
        'total_price': summary['total_price'],
        'final_price': summary['final_price'],
    }
    return render(request, 'cart/cart.html', context)


@login_required
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id, status='published')
    if not product.is_available:
        return JsonResponse({'success': False, 'message': 'این فایل در حال حاضر قابل خرید نیست.'}, status=400)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    # محصولات دیجیتال کمّیت ندارند؛ هر فایل فقط یک‌بار به سبد اضافه می‌شود.
    _, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': 1})
    if not created:
        return JsonResponse({'success': False, 'message': 'این فایل از قبل در سبد خرید شما موجود است.'}, status=409)

    return JsonResponse({
        'success': True,
        'message': 'فایل با موفقیت به سبد خرید اضافه شد.',
        'cart_count': cart.items.count(),
    })


@login_required
@require_POST
def remove_cart_item(request, item_id):
    cart_item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
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

            coupon = Coupon.objects.select_for_update().get(code__iexact=coupon_code)
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

    from payments.models import GatewaySettings
    context = {
        'cart': summary['cart'],
        'cart_items': summary['cart_items'],
        'total_price': summary['total_price'],
        'final_price': summary['final_price'],
        # درگاهِ پیاده‌سازی‌نشده (مثل اسنپ‌پی تا پیش از قرارداد) هرگز به مشتری
        # پیشنهاد نمی‌شود؛ درگاهِ فعالِ پیکربندی‌نشده در شروع پرداخت با پیام
        # روشن رد می‌شود و اینجا می‌ماند تا مدیر متوجه ناقص‌بودن تنظیمات شود.
        'enabled_gateways': [
            gateway for gateway in GatewaySettings.objects.filter(is_enabled=True)
            if gateway.is_implemented
        ],
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
