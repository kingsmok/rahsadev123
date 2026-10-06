from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from cart.models import Cart, Order, OrderItem
from downloads.models import DownloadToken
from dashboard.models import Notification
from .services import GATEWAYS
from .models import GatewaySettings, PaymentTransaction


def _complete(tx, ref_id='', response=None):
    """پس از تأیید پرداخت: سفارش پرداخت‌شده، فایل‌ها آماده دانلود و سبد خالی می‌شود."""
    with db_transaction.atomic():
        tx.status, tx.ref_id, tx.raw_response = 'paid', str(ref_id), response or {}
        tx.save(update_fields=['status', 'ref_id', 'raw_response', 'updated_at'])
        order = tx.order
        if order.status == 'pending':
            order.status = 'paid'
            order.save(update_fields=['status', 'updated_at'])
            for item in order.cart.items.select_related('product').all() if order.cart else []:
                OrderItem.objects.create(order=order, product=item.product, title_snapshot=item.product.title, unit_price=item.product.price, quantity=item.quantity, total_price=item.total_price)
                if not item.product.is_unlimited:
                    item.product.stock_count = max(0, item.product.stock_count - item.quantity)
                item.product.sales_count += item.quantity
                item.product.save(update_fields=['stock_count', 'sales_count'])
                if hasattr(item.product, 'digital_asset'):
                    DownloadToken.objects.create(user=order.user, product=item.product, order=order)
            notification = Notification.objects.create(
                message=f'پرداخت سفارش {order.order_number} انجام شد؛ فایل‌های شما آماده دانلود است.',
            )
            notification.users.set([order.user])
            if order.cart:
                order.cart.delete()
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

        # اگر سفارش pending همین سبد از قبل وجود دارد، دوباره نساز (خطای قبلی درگاه و ...)
        order = Order.objects.filter(user=request.user, cart=cart, status='pending').first()
        if order is None:
            total = sum(item.total_price for item in items)
            # محصولات دیجیتال هزینه ارسال ندارند؛ تحویل به‌صورت آنی انجام می‌شود.
            order = Order.objects.create(
                user=request.user, cart=cart, total_price=total,
                coupon_discount=cart.coupon_discount, shipping_cost=0,
                final_price=total - cart.coupon_discount, status='pending',
            )
    else:
        order = get_object_or_404(Order, order_number=order_number, user=request.user)

    gateway = request.POST.get('gateway', 'zarinpal')
    if gateway not in dict(PaymentTransaction.GATEWAYS):
        gateway = 'zarinpal'

    # فقط درگاه‌های فعال‌شده در پنل مدیریت قابل استفاده‌اند
    gs = GatewaySettings.objects.filter(key=gateway).first()
    if not gs or not gs.is_enabled:
        gateway_title = gs.title if gs else 'انتخاب‌شده'
        messages.error(request, f'درگاه «{gateway_title}» در حال حاضر غیرفعال است.')
        return redirect('cart:shopping_payment')

    tx = PaymentTransaction.objects.create(order=order, gateway=gateway, amount=order.final_price)
    try:
        callback = request.build_absolute_uri(reverse('payments:callback'))
        authority, url = GATEWAYS[gateway].start(tx, callback)
        tx.authority, tx.status = authority, 'redirected'
        tx.save(update_fields=['authority', 'status', 'updated_at'])
        return redirect(url)
    except Exception as exc:
        tx.status, tx.raw_response = 'failed', {'error': str(exc)}
        tx.save(update_fields=['status', 'raw_response', 'updated_at'])
        messages.error(request, f'اتصال به درگاه انجام نشد: {exc}')
        return redirect('cart:shopping_payment')


@login_required
def callback(request):
    authority = request.GET.get('Authority', '')
    tx = get_object_or_404(PaymentTransaction, authority=authority, order__user=request.user)
    if request.GET.get('Status') != 'OK':
        tx.status = 'failed'; tx.save(update_fields=['status', 'updated_at'])
        return HttpResponse('پرداخت لغو شد.', status=400)
    try:
        valid, data = GATEWAYS[tx.gateway].verify(tx, request.GET)
    except Exception as exc:
        valid, data = False, {'error': str(exc)}
    if not valid:
        tx.status, tx.raw_response = 'failed', data
        tx.save(update_fields=['status', 'raw_response', 'updated_at'])
        return HttpResponse('تأیید پرداخت ناموفق بود.', status=400)
    order = _complete(tx, data.get('ref_id', ''), data)
    return redirect('payments:successful_done', order_number=order.order_number)


@login_required
def successful_payment_done(request, order_number):
    """صفحه پایان خرید؛ فایل‌های سفارش پرداخت‌شده آماده دانلود است."""
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    if order.status != 'paid':
        return redirect('dashboard:order_detail', order_number=order.order_number)
    tokens = DownloadToken.objects.filter(order=order, user=request.user).select_related('product')
    return render(request, 'cart/successful_payment.html', {'order': order, 'tokens': tokens})
