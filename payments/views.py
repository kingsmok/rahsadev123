from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from cart.models import Order
from .models import PaymentTransaction


@login_required
def start_payment(request, order_number):
    if order_number == 'new':
        from cart.models import Cart
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
    # Adapters are deliberately configuration-driven: credentials are never hard-coded.
    # The integration endpoint can be enabled per gateway in settings/environment.
    if gateway == 'zarinpal':
        return redirect(f'https://www.zarinpal.com/pg/StartPay/{tx.pk}')
    return HttpResponse(f'درگاه {tx.get_gateway_display()} انتخاب شد. تنظیمات اتصال در محیط اجرا تکمیل نشده است.', status=503)


@login_required
def callback(request):
    authority = request.GET.get('Authority', '')
    tx = PaymentTransaction.objects.filter(authority=authority).first()
    if not tx:
        return HttpResponse('تراکنش پیدا نشد.', status=404)
    return redirect('cart:successful_payment')
