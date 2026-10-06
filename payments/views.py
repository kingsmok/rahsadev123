from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from cart.models import Cart, Order, OrderItem
from downloads.models import DownloadToken
from dashboard.models import Notification
from product.models import Product
from .services import GATEWAYS
from .models import GatewaySettings, PaymentTransaction


def _normalised_order_items(order):
    """Return the immutable item snapshot saved when an order was created.

    A cart remains editable while a customer is on the payment gateway.  The
    gateway callback must therefore fulfil the order snapshot, not whatever is
    currently in that cart.
    """
    items_data = order.items_data or {}
    raw_items = items_data.get('items', []) if isinstance(items_data, dict) else items_data
    if not isinstance(raw_items, list):
        return []

    items = []
    seen_product_ids = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        try:
            product_id = int(raw_item.get('product_id', raw_item.get('product')))
            quantity = int(raw_item.get('quantity', 1))
            unit_price = int(raw_item.get('unit_price', raw_item.get('price', 0)))
        except (TypeError, ValueError):
            continue
        if product_id <= 0 or quantity <= 0 or unit_price < 0 or product_id in seen_product_ids:
            continue
        seen_product_ids.add(product_id)
        items.append({
            'product_id': product_id,
            'quantity': quantity,
            'unit_price': unit_price,
            'title': str(raw_item.get('title') or raw_item.get('product_title') or ''),
        })
    return items


def _cart_matches_order_snapshot(cart, order):
    """Whether a pending order can safely be reused for the live cart."""
    snapshot = _normalised_order_items(order)
    cart_items = list(cart.items.select_related('product').all())
    if len(snapshot) != len(cart_items):
        return False

    current = sorted(
        (item.product_id, item.quantity, item.product.price)
        for item in cart_items
    )
    saved = sorted(
        (item['product_id'], item['quantity'], item['unit_price'])
        for item in snapshot
    )
    return (
        current == saved
        and order.total_price == sum(item.total_price for item in cart_items)
        and order.coupon_discount == cart.coupon_discount
        and order.final_price == cart.final_price
    )


def _complete(tx, ref_id='', response=None):
    """Atomically fulfil exactly the items that were paid for.

    The callback can be retried by a gateway, and a customer can change their
    cart in another tab while the gateway is open.  Lock the transaction and
    order, use the stored order snapshot, and only remove those paid items from
    a changed cart.  This keeps delivery, stock, order history and cart totals
    consistent without relying on client-side state.
    """
    with db_transaction.atomic():
        transaction = (
            PaymentTransaction.objects.select_for_update()
            .select_related('order', 'order__cart')
            .get(pk=tx.pk)
        )
        order = Order.objects.select_for_update().select_related('cart').get(pk=transaction.order_id)

        # A repeated callback must never create another OrderItem, token or
        # stock decrement.  It is still safe to record the provider reference.
        if order.status == 'paid':
            if transaction.status != 'paid' or transaction.ref_id != str(ref_id):
                transaction.status = 'paid'
                transaction.ref_id = str(ref_id)
                transaction.raw_response = response or {}
                transaction.save(update_fields=['status', 'ref_id', 'raw_response', 'updated_at'])
            return order

        if order.status != 'pending':
            # Do not silently turn a cancelled/processing order into a paid
            # fulfilment.  Staff can reconcile this exceptional gateway result
            # from the transaction record.
            transaction.status = 'failed'
            transaction.raw_response = {
                **(response or {}),
                'error': f'order is {order.status}, not pending',
            }
            transaction.save(update_fields=['status', 'raw_response', 'updated_at'])
            return order

        snapshot = _normalised_order_items(order)
        if not snapshot:
            raise ValueError('سفارش پرداختی فاقد اطلاعات معتبر محصول است.')

        product_ids = [item['product_id'] for item in snapshot]
        products = {
            product.pk: product
            for product in (
                Product.objects.select_for_update()
                .select_related('digital_asset')
                .filter(pk__in=product_ids)
            )
        }
        missing_products = set(product_ids) - set(products)
        if missing_products:
            raise ValueError('یکی از محصولات این سفارش دیگر در دسترس نیست.')

        transaction.status = 'paid'
        transaction.ref_id = str(ref_id)
        transaction.raw_response = response or {}
        transaction.save(update_fields=['status', 'ref_id', 'raw_response', 'updated_at'])

        for item in snapshot:
            product = products[item['product_id']]
            quantity = item['quantity']
            unit_price = item['unit_price']
            OrderItem.objects.get_or_create(
                order=order,
                product=product,
                defaults={
                    'title_snapshot': item['title'] or product.title,
                    'unit_price': unit_price,
                    'quantity': quantity,
                    'total_price': unit_price * quantity,
                },
            )

            if not product.is_unlimited:
                product.stock_count = max(0, product.stock_count - quantity)
            product.sales_count += quantity
            product.save(update_fields=['stock_count', 'sales_count'])

            if getattr(product, 'digital_asset', None) is not None:
                DownloadToken.objects.get_or_create(user=order.user, product=product, order=order)

        order.status = 'paid'
        order.save(update_fields=['status', 'updated_at'])
        notification = Notification.objects.create(
            message=f'پرداخت سفارش {order.order_number} انجام شد؛ فایل‌های شما آماده دانلود است.',
        )
        notification.users.set([order.user])

        cart = order.cart
        if cart:
            paid_product_ids = set(product_ids)
            current_signature = sorted((item.product_id, item.quantity) for item in cart.items.all())
            paid_signature = sorted((item['product_id'], item['quantity']) for item in snapshot)

            # A second pending checkout for the same cart cannot later fulfil
            # the same items after this payment has succeeded.
            Order.objects.filter(user=order.user, cart=cart, status='pending').exclude(pk=order.pk).update(
                status='cancelled'
            )

            if current_signature == paid_signature:
                cart.delete()
            else:
                # Keep products added after checkout, but never leave a coupon
                # discount from the paid snapshot attached to those new items.
                cart.items.filter(product_id__in=paid_product_ids).delete()
                cart.coupon = None
                cart.coupon_discount = 0
                cart.save(update_fields=['coupon', 'coupon_discount', 'updated_at'])

    return order


@login_required
def start_payment(request, order_number):
    if request.method != 'POST':
        return HttpResponse('روش پرداخت باید با درخواست معتبر ارسال شود.', status=405)
    if order_number == 'new':
        cart = get_object_or_404(Cart, user=request.user)
        items = list(cart.items.select_related('product').all())
        if not items:
            return redirect('cart:cart')
        if any(item.product.status != 'published' or not item.product.is_available for item in items):
            messages.error(request, 'یکی از فایل‌های سبد دیگر برای خرید در دسترس نیست. لطفاً سبد را به‌روزرسانی کنید.')
            return redirect('cart:cart')

        # Reuse only an order whose immutable snapshot still matches the cart.
        # A stale pending order must never charge an updated cart total.
        order = Order.objects.filter(user=request.user, cart=cart, status='pending').order_by('-created_at').first()
        if order is None or not _cart_matches_order_snapshot(cart, order):
            total = sum(item.total_price for item in items)
            order = Order.objects.create(
                user=request.user,
                cart=cart,
                total_price=total,
                coupon_discount=min(cart.coupon_discount, total),
                shipping_cost=0,
                final_price=cart.final_price,
                status='pending',
            )
    else:
        order = get_object_or_404(Order, order_number=order_number, user=request.user)

    gateway = request.POST.get('gateway', 'zarinpal')
    if gateway not in dict(PaymentTransaction.GATEWAYS):
        gateway = 'zarinpal'

    # Only gateways enabled by staff can be used.  A configured environment
    # credential is accepted as well as a credential saved in the admin panel.
    gateway_settings = GatewaySettings.objects.filter(key=gateway).first()
    if not gateway_settings or not gateway_settings.is_enabled:
        gateway_title = gateway_settings.title if gateway_settings else 'انتخاب‌شده'
        messages.error(request, f'درگاه «{gateway_title}» در حال حاضر غیرفعال است.')
        return redirect('cart:shopping_payment')
    if not gateway_settings.is_configured:
        messages.error(request, f'اطلاعات اتصال درگاه «{gateway_settings.title}» کامل نشده است.')
        return redirect('cart:shopping_payment')

    transaction = PaymentTransaction.objects.create(order=order, gateway=gateway, amount=order.final_price)
    try:
        callback = request.build_absolute_uri(reverse('payments:callback'))
        authority, url = GATEWAYS[gateway].start(transaction, callback)
        transaction.authority, transaction.status = authority, 'redirected'
        transaction.save(update_fields=['authority', 'status', 'updated_at'])
        return redirect(url)
    except Exception as exc:
        transaction.status, transaction.raw_response = 'failed', {'error': str(exc)}
        transaction.save(update_fields=['status', 'raw_response', 'updated_at'])
        messages.error(request, f'اتصال به درگاه انجام نشد: {exc}')
        return redirect('cart:shopping_payment')


@login_required
def callback(request):
    authority = (request.GET.get('Authority') or '').strip()
    if not authority:
        return HttpResponse('شناسه پرداخت نامعتبر است.', status=400)
    transaction = get_object_or_404(PaymentTransaction, authority=authority, order__user=request.user)
    if request.GET.get('Status') != 'OK':
        transaction.status = 'failed'
        transaction.save(update_fields=['status', 'updated_at'])
        return HttpResponse('پرداخت لغو شد.', status=400)
    try:
        valid, data = GATEWAYS[transaction.gateway].verify(transaction, request.GET)
    except Exception as exc:
        valid, data = False, {'error': str(exc)}
    if not valid:
        transaction.status, transaction.raw_response = 'failed', data
        transaction.save(update_fields=['status', 'raw_response', 'updated_at'])
        return HttpResponse('تأیید پرداخت ناموفق بود.', status=400)
    order = _complete(transaction, data.get('ref_id', ''), data)
    return redirect('payments:successful_done', order_number=order.order_number)


@login_required
def successful_payment_done(request, order_number):
    """صفحه پایان خرید؛ فایل‌های سفارش پرداخت‌شده آماده دانلود است."""
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    if order.status != 'paid':
        return redirect('dashboard:order_detail', order_number=order.order_number)
    tokens = DownloadToken.objects.filter(order=order, user=request.user).select_related('product')
    return render(request, 'cart/successful_payment.html', {'order': order, 'tokens': tokens})
