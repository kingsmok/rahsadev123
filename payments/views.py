from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from cart.models import Cart, Order, OrderItem
from downloads.models import DownloadToken
from .services import GATEWAYS
from .models import PaymentTransaction


def _complete(tx, ref_id='', response=None):
    with transaction.atomic():
        tx.status, tx.ref_id, tx.raw_response = 'paid', str(ref_id), response or {}
        tx.save(update_fields=['status', 'ref_id', 'raw_response', 'updated_at'])
        order = tx.order
        if order.status == 'pending':
            order.status = 'paid'
            order.save(update_fields=['status', 'updated_at'])
            for item in order.cart.items.select_related('product').all() if order.cart else []:
                OrderItem.objects.create(order=order, product=item.product, title_snapshot=item.product.title, unit_price=item.product.price, quantity=item.quantity, total_price=item.total_price)
                item.product.stock_count = max(0, item.product.stock_count - item.quantity)
                item.product.sales_count += item.quantity
                item.product.save(update_fields=['stock_count', 'sales_count'])
                if hasattr(item.product, 'digital_asset'):
                    DownloadToken.objects.create(user=order.user, product=item.product, order=order)
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
        total = sum(item.total_price for item in items)
        shipping = 50000 if total < 10500000 else 0
        order = Order.objects.create(user=request.user, address=request.user.addresses.filter(is_default=True).first(), cart=cart, total_price=total, coupon_discount=cart.coupon_discount, shipping_cost=shipping, final_price=total - cart.coupon_discount + shipping, status='pending')
    else:
        order = get_object_or_404(Order, order_number=order_number, user=request.user)
    gateway = request.POST.get('gateway', 'zarinpal')
    if gateway not in dict(PaymentTransaction.GATEWAYS):
        gateway = 'zarinpal'
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
        return HttpResponse(f'اتصال به درگاه انجام نشد: {exc}', status=503)


@login_required
def callback(request):
    authority = request.GET.get('Authority', '')
    tx = get_object_or_404(PaymentTransaction, authority=authority)
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
    return redirect('dashboard:order_detail', order_number=order.order_number)
