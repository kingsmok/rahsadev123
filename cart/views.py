from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from .models import Cart, CartItem, Coupon, Order
from product.models import Product
from django.db import transaction as db_transaction
from django.views.decorators.http import require_POST


def _cart_summary(user):
    """جمع سبد خرید دیجیتال (بدون هزینه ارسال)."""
    cart = Cart.objects.filter(user=user).first()
    items = list(cart.items.select_related('product')) if cart else []
    total_price = sum(item.total_price for item in items)
    return {
        'cart': cart,
        'cart_items': items,
        'total_price': total_price,
        'coupon_discount': cart.coupon_discount if cart else 0,
        'final_price': max(0, total_price - (cart.coupon_discount if cart else 0)),
    }


def _discount_amount(coupon, total_price):
    """مبلغ تخفیف یک کوپن برای یک جمع مشخص (هرگز منفی یا بیش از جمع سبد)."""
    if coupon.discount_type == 'percentage':
        discount = int((total_price * coupon.discount_value) / 100)
    else:
        discount = coupon.discount_value
    if coupon.maximum_discount:
        discount = min(discount, coupon.maximum_discount)
    return max(0, min(discount, total_price))


def _revalidate_coupon(cart, items):
    """Recompute the applied coupon against the cart's *current* contents.

    A discount is calculated from the cart total at the time it is applied.  If
    the customer then removes the expensive item that justified it, the stale
    amount must not survive: left untouched, a 500,000 discount on a 100,000
    cart makes the order payable for zero.  Re-run the same rules here and drop
    the coupon when it no longer qualifies.

    The coupon's global ``usage_count`` is deliberately left as it was:
    ``apply_coupon`` reserves one use per application, so a reserved use stays
    reserved even if the cart changes afterwards.
    """
    if cart is None or cart.coupon is None:
        return

    coupon = cart.coupon
    total_price = sum(item.total_price for item in items)
    now = timezone.now()

    still_valid = (
        bool(items)
        and coupon.is_active
        and coupon.valid_from <= now <= coupon.valid_to
        and (not coupon.minimum_order_amount or total_price >= coupon.minimum_order_amount)
    )

    if still_valid:
        new_coupon, new_discount = coupon, _discount_amount(coupon, total_price)
    else:
        new_coupon, new_discount = None, 0

    # ``cart`` is revalidated on every page view, so only touch the database
    # when the stored values really are stale.
    if cart.coupon_id == (new_coupon.pk if new_coupon else None) \
            and cart.coupon_discount == new_discount:
        return

    cart.coupon = new_coupon
    cart.coupon_discount = new_discount
    cart.save(update_fields=['coupon', 'coupon_discount', 'updated_at'])


@login_required
def cart(request):
    summary = _cart_summary(request.user)

    # محتویات سبد می‌تواند از آخرین باری که تخفیف اعمال شده تغییر کرده باشد
    # (مثلاً حذف آیتم در یک تب دیگر)؛ تخفیف را دوباره با جمع فعلی بسنجیم.
    _revalidate_coupon(summary['cart'], summary['cart_items'])

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
    _revalidate_coupon(cart, remaining_items)

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
            if not coupon.is_valid():
                messages.error(request, 'کد تخفیف معتبر نیست یا منقضی شده است')
                return redirect('cart:cart')

            if cart.coupon:
                messages.warning(request, 'یک کد تخفیف قبلاً اعمال شده است')
                return redirect('cart:cart')

            if coupon.per_user_limit and _paid_coupon_uses(request.user, coupon) >= coupon.per_user_limit:
                messages.error(request, 'سقف استفاده شما از این کد تخفیف تکمیل شده است.')
                return redirect('cart:cart')

            total_price = sum(item.total_price for item in cart.items.select_related('product'))
            if coupon.minimum_order_amount and total_price < coupon.minimum_order_amount:
                messages.error(request, f'حداقل مبلغ سفارش برای این کد تخفیف {coupon.minimum_order_amount:,} تومان است')
                return redirect('cart:cart')

            discount = _discount_amount(coupon, total_price)

            cart.coupon = coupon
            cart.coupon_discount = discount
            cart.save(update_fields=['coupon', 'coupon_discount', 'updated_at'])

            # Applying a coupon reserves one of its global uses.  This keeps a
            # final-use coupon from being granted simultaneously in two carts.
            coupon.usage_count += 1
            if coupon.max_usage and coupon.usage_count >= coupon.max_usage:
                coupon.is_active = False
            coupon.save(update_fields=['usage_count', 'is_active'])

        messages.success(request, f'کد تخفیف {coupon.code} با موفقیت اعمال شد ({discount:,} تومان تخفیف)')
    except Coupon.DoesNotExist:
        messages.error(request, 'کد تخفیف وارد شده معتبر نیست')
    return redirect('cart:cart')


@login_required
def shopping_payment(request):
    summary = _cart_summary(request.user)
    if not summary['cart_items']:
        messages.warning(request, 'سبد خرید شما خالی است')
        return redirect('cart:cart')

    from payments.models import GatewaySettings
    context = {
        'cart': summary['cart'],
        'cart_items': summary['cart_items'],
        'total_price': summary['total_price'],
        'final_price': summary['final_price'],
        'enabled_gateways': GatewaySettings.objects.filter(is_enabled=True),
    }
    return render(request, 'cart/shopping_payment.html', context)


@login_required
def successful_payment(request):
    messages.info(request, 'برای ثبت سفارش، ابتدا از یکی از درگاه‌های پرداخت استفاده کنید.')
    return redirect('cart:shopping_payment')
