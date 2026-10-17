import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.contrib.auth.views import redirect_to_login
from django.db import transaction as db_transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from cart.coupons import release_coupon_reservation, revalidate_coupon
from cart.guest import (
    SESSION_ACCOUNT_KEY, SESSION_ERRORS_KEY, can_access_order, get_cart, grant_order_access,
    remember_checkout_details,
)
from cart.models import Order, OrderItem
from downloads.models import DownloadToken
from dashboard.models import Notification
from product.models import Product
from .gateways import CHECKOUT_REDIRECT_ORIGINS, _origin
from .services import GATEWAY_CALLBACK_KEYS, GATEWAYS, MOBILE_REQUIRED_KEYS
from .models import GatewaySettings, PaymentTransaction

logger = logging.getLogger(__name__)


class FulfilmentError(RuntimeError):
    """The gateway confirmed a payment that the order cannot be fulfilled for.

    Raised inside the atomic block of :func:`_complete`, so the caller is
    responsible for recording the failure: the money has already been taken and
    must stay reconcilable from the transaction record.
    """


class DuplicatePaymentError(FulfilmentError):
    """A second, separately charged payment arrived for an order that is already paid.

    It used to be recorded as just another successful payment, so a customer who
    paid the same order in two tabs was charged twice without anyone noticing.
    It now lands in the refund queue (``PaymentTransaction.objects.unfulfilled``)
    and staff are notified.
    """


#: A second submit of the payment form within this window (double click, back
#: + resubmit) is sent to the gateway page already opened for the same order
#: instead of opening another payment at the provider.
PAYMENT_REUSE_WINDOW = timedelta(minutes=2)


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
            if transaction.status != 'paid' and PaymentTransaction.objects.filter(
                order=order, status='paid',
            ).exclude(pk=transaction.pk).exists():
                raise DuplicatePaymentError(
                    'این سفارش پیش‌تر با تراکنش دیگری پرداخت شده بود؛ این پرداخت تکراری است و باید بازگردانده شود.'
                )
            if transaction.status != 'paid' or transaction.ref_id != str(ref_id):
                transaction.status = 'paid'
                transaction.ref_id = str(ref_id)
                transaction.raw_response = response or {}
                transaction.save(update_fields=['status', 'ref_id', 'raw_response', 'updated_at'])
            return order

        if order.status != 'pending':
            # The gateway has confirmed and charged this payment, but the order
            # is no longer payable (the customer asked to cancel it, or staff
            # cancelled it) while they were away on the provider's page.
            #
            # Recording this as a plain "failed" transaction would be wrong: the
            # money *was* taken, so staff reconciling failures would refund a
            # payment that actually succeeded.  Let the callback persist it as
            # verified-but-unfulfilled and tell the customer what happened.
            raise FulfilmentError(
                f'سفارش در وضعیت «{order.get_status_display()}» است و پرداخت آن '
                f'نمی‌تواند به‌طور خودکار تحویل داده شود.'
            )

        snapshot = _normalised_order_items(order)
        if not snapshot:
            raise FulfilmentError('سفارش پرداختی فاقد اطلاعات معتبر محصول است.')

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
            raise FulfilmentError('یکی از محصولات این سفارش دیگر در دسترس نیست.')

        # Stock is only checked at checkout start, so two customers can both be
        # on the gateway while a single licence is left.  These rows are locked,
        # so re-checking here (before any download token is issued) is the last
        # point at which overselling a limited licence can still be prevented.
        insufficient = [
            product.title
            for product in products.values()
            if not product.is_unlimited and product.stock_count < sum(
                item['quantity'] for item in snapshot
                if item['product_id'] == product.pk
            )
        ]
        if insufficient:
            raise FulfilmentError(
                'موجودی «%s» کافی نیست و پرداخت قابل تحویل نیست.' % '، '.join(insufficient)
            )

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
                # ``user`` is empty for a guest order; its tokens are then opened
                # through the order's session/secret link (downloads.views).
                DownloadToken.objects.get_or_create(user=order.user, product=product, order=order)

        order.status = 'paid'
        order.save(update_fields=['status', 'updated_at'])
        order.just_completed = True
        if order.user_id:
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
            Order.objects.filter(cart=cart, status='pending').exclude(pk=order.pk).update(
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


def _order_page_url(order):
    """Where the customer reviews an order: the dashboard, or the guest order page."""
    if order.user_id:
        return reverse('dashboard:order_detail', kwargs={'order_number': order.order_number})
    return reverse('cart:guest_order', kwargs={'access_token': order.access_token})


def _retry_url(order):
    """After a cancelled or failed payment: back to checkout while the cart still holds the files."""
    cart = order.cart
    if cart is not None and cart.items.exists():
        return reverse('cart:shopping_payment')
    return _order_page_url(order)


def _after_payment(request, order):
    """Follow-up for an order paid *in this request*: the guest's receipt e-mail.

    Deliberately never writes ``request.session``: Snapp Pay and Torob Pay come
    back with a cross-site POST that carries no session cookie, and creating a
    session there would replace the buyer's real session cookie.
    """
    if not getattr(order, 'just_completed', False) or order.user_id is not None or not order.contact_email:
        return
    from notifications.services import absolute_url, schedule_guest_order_email

    path = _order_page_url(order)
    link = absolute_url(path)
    if not link.startswith('http'):
        link = request.build_absolute_uri(path)
    schedule_guest_order_email(order.pk, link)


def _complete_free_order(request, order):
    """Fulfil an order whose payable amount is zero without any gateway.

    A coupon may cover the whole cart (the discount is capped at the cart
    total).  Gateways refuse a zero amount, so such an order used to end on
    "could not connect to the payment gateway, please retry" forever.  The
    normal fulfilment path (``_complete``: snapshot, stock, download tokens,
    notification, cart cleanup) is reused with a ``free`` transaction record.
    """
    transaction = PaymentTransaction.objects.create(order=order, gateway='free', amount=0)
    try:
        order = _complete(transaction, ref_id=f'FREE-{order.order_number}', response={'free_order': True})
    except FulfilmentError as exc:
        # Nothing was charged, so this is not a refund case: record and explain.
        logger.warning('Free order %s could not be fulfilled: %s', order.order_number, exc)
        PaymentTransaction.objects.filter(pk=transaction.pk).update(
            status='failed', raw_response={'free_order': True, 'error': str(exc)},
        )
        messages.error(request, f'ثبت سفارش انجام نشد: {exc}')
        return redirect('cart:cart')
    _after_payment(request, order)
    messages.success(request, 'سفارش شما با کد تخفیف به‌طور کامل پوشش داده شد و فایل‌ها آماده دانلود است.')
    return redirect('payments:successful_done', order_number=order.order_number)


def _start_gateway(adapter, transaction, callback, customer):
    """Pass customer details only to adapters whose ``start`` accepts them."""
    import inspect

    try:
        params = inspect.signature(adapter.start).parameters
    except (TypeError, ValueError):
        params = {}
    if 'customer' in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return adapter.start(transaction, callback, customer=customer)
    return adapter.start(transaction, callback)


def _customer_details(request):
    """Mobile/e-mail for gateways that need them; a mobile typed on the payment
    page is also saved to an empty profile phone for next time."""
    from notifications.sms import normalize_mobile

    profile = getattr(request.user, 'profile', None)
    typed = normalize_mobile(request.POST.get('mobile', ''))
    stored = normalize_mobile(getattr(profile, 'phone', '') or '')
    mobile = typed or stored
    if typed and profile is not None and not stored:
        profile.phone = typed
        profile.save(update_fields=['phone'])
    return {
        'mobile': mobile,
        'email': request.user.email or getattr(profile, 'email', '') or '',
        'full_name': request.user.get_full_name(),
    }


def _guest_customer(order):
    """A guest's contact for the gateway comes from the validated checkout form."""
    return {'mobile': order.contact_mobile, 'email': order.contact_email, 'full_name': ''}


def _guest_details(request):
    """Validate the guest checkout fields (PRG: errors and values go back via the session)."""
    from cart.forms import GuestCheckoutForm
    from cart.views import _otp_available

    password_mode = not _otp_available()
    form = GuestCheckoutForm(request.POST, password_mode=password_mode)
    valid = form.is_valid()
    data = form.cleaned_data if valid else {}
    remember_checkout_details(
        request,
        mobile=data.get('mobile') or (request.POST.get('mobile') or '').strip()[:20],
        email=data.get('email') or (request.POST.get('email') or '').strip()[:254],
        create_account=bool(request.POST.get('create_account')),
    )
    if not valid:
        request.session[SESSION_ERRORS_KEY] = form.error_dict()
    return valid, data, password_mode


def _authorize_order(request, order):
    """``None`` when the visitor may act on ``order``; otherwise the response to return."""
    if order.user_id:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.pk != order.user_id:
            raise Http404
        return None
    if not can_access_order(request, order):
        raise Http404
    return None


def _gateway_redirect(request, url, title):
    if _origin(url) in CHECKOUT_REDIRECT_ORIGINS:
        return redirect(url)
    # Payment page on an origin the CSP ``form-action`` does not list
    # (Snapp Pay / Torob Pay hand out their page URL at runtime): continue
    # with a navigation instead of a redirect of this form POST.
    return render(request, 'payments/redirect_to_gateway.html', {
        'gateway_url': url,
        'gateway_title': title,
    })


def _enforce_per_customer_coupon_limit(request, cart, guest_data):
    """Re-check a coupon's per-customer limit at payment time; drop it when used up.

    For a guest it can only be checked here, once the mobile/e-mail typed at
    checkout identifies the customer.  Returns ``True`` when the coupon was dropped.
    """
    from cart.views import _paid_coupon_uses, paid_coupon_uses_by_contact

    coupon = cart.coupon
    if coupon is None or not coupon.per_user_limit:
        return False
    if guest_data is not None:
        uses = paid_coupon_uses_by_contact(coupon, guest_data.get('mobile', ''), guest_data.get('email', ''))
    else:
        uses = _paid_coupon_uses(request.user, coupon)
    if uses < coupon.per_user_limit:
        return False
    release_coupon_reservation(coupon)
    cart.coupon = None
    cart.coupon_discount = 0
    cart.save(update_fields=['coupon', 'coupon_discount', 'updated_at'])
    return True


@never_cache
def start_payment(request, order_number):
    if request.method != 'POST':
        return HttpResponse('روش پرداخت باید با درخواست معتبر ارسال شود.', status=405)
    guest = not request.user.is_authenticated
    if order_number == 'new':
        cart = get_cart(request)
        items = list(cart.items.select_related('product').all()) if cart is not None else []
        if not items:
            return redirect('cart:cart')
        if any(item.product.status != 'published' or not item.product.is_available for item in items):
            messages.error(request, 'یکی از فایل‌های سبد دیگر برای خرید در دسترس نیست. لطفاً سبد را به‌روزرسانی کنید.')
            return redirect('cart:cart')

        guest_data = None
        password_mode = False
        if guest:
            valid, guest_data, password_mode = _guest_details(request)
            if not valid:
                messages.error(request, 'لطفاً اطلاعات خریدار را بررسی و اصلاح کنید.')
                return redirect(reverse('cart:shopping_payment') + '#checkout-details')

        # The coupon may have expired or been disabled since the payment page
        # was rendered.  Never charge a total the customer has not seen: show
        # the corrected amount and let them confirm it.
        if revalidate_coupon(cart, items):
            messages.warning(
                request,
                'کد تخفیف سبد شما دیگر معتبر نیست یا مبلغ آن تغییر کرده است؛ مبلغ قابل پرداخت '
                'به‌روزرسانی شد. لطفاً آن را بررسی و دوباره پرداخت کنید.',
            )
            return redirect('cart:shopping_payment')
        if _enforce_per_customer_coupon_limit(request, cart, guest_data):
            messages.error(
                request,
                'سقف استفادهٔ شما از این کد تخفیف تکمیل شده است؛ کد از سبد حذف شد و مبلغ قابل پرداخت '
                'به‌روزرسانی شد. لطفاً آن را بررسی و دوباره پرداخت کنید.',
            )
            return redirect('cart:shopping_payment')

        if guest:
            contact = {'contact_mobile': guest_data['mobile'], 'contact_email': guest_data['email'],
                       'create_account_requested': bool(guest_data.get('create_account'))}
        else:
            from notifications.sms import normalize_mobile

            profile = getattr(request.user, 'profile', None)
            contact = {
                'contact_mobile': normalize_mobile(request.POST.get('mobile', '')) or normalize_mobile(getattr(profile, 'phone', '') or ''),
                'contact_email': (request.user.email or getattr(profile, 'email', '') or '')[:254],
            }

        # Reuse only an order whose immutable snapshot still matches the cart.
        # A stale pending order must never charge an updated cart total.
        order = (
            Order.objects.filter(cart=cart, status='pending', user=None if guest else request.user)
            .order_by('-created_at').first()
        )
        if order is None or not _cart_matches_order_snapshot(cart, order):
            total = sum(item.total_price for item in items)
            order = Order.objects.create(
                user=None if guest else request.user,
                cart=cart,
                total_price=total,
                coupon_discount=min(cart.coupon_discount, total),
                shipping_cost=0,
                final_price=cart.final_price,
                status='pending',
                **contact,
            )
        else:
            changed = [field for field, value in contact.items() if getattr(order, field) != value]
            if changed:
                for field in changed:
                    setattr(order, field, contact[field])
                order.save(update_fields=changed + ['updated_at'])

        if guest:
            grant_order_access(request, order)
            pending_accounts = dict(request.session.get(SESSION_ACCOUNT_KEY) or {})
            pending_accounts.pop(str(order.pk), None)
            if guest_data.get('create_account') and password_mode and guest_data.get('password'):
                # Only a hash, and only until the order is paid (or abandoned with the session).
                pending_accounts[str(order.pk)] = make_password(guest_data['password'])
            request.session[SESSION_ACCOUNT_KEY] = pending_accounts
    else:
        # A payment may only be started for an order that is still awaiting one.
        # Without this check a customer could open ``/payments/start/<number>/``
        # for an order that is already paid (or cancelled) and be charged twice
        # for the same download.
        order = get_object_or_404(Order, order_number=order_number)
        denied = _authorize_order(request, order)
        if denied is not None:
            return denied
        if order.status != 'pending':
            if order.status == 'paid':
                messages.info(request, 'این سفارش قبلاً پرداخت شده است و فایل‌های آن آماده دانلود است.')
                return redirect('payments:successful_done', order_number=order.order_number)
            if order.status == 'cancelled':
                messages.error(request, 'این سفارش لغو شده است و امکان پرداخت آن وجود ندارد.')
                return redirect(_order_page_url(order))
            messages.info(request, f'وضعیت این سفارش «{order.get_status_display()}» است و در حال حاضر قابل پرداخت نیست.')
            return redirect(_order_page_url(order))

    if order.final_price == 0:
        return _complete_free_order(request, order)

    gateway = request.POST.get('gateway', 'zarinpal')
    if gateway not in GATEWAYS:
        gateway = 'zarinpal'

    # Only gateways enabled by staff can be used.  A configured environment
    # credential is accepted as well as a credential saved in the admin panel.
    gateway_settings = GatewaySettings.objects.filter(key=gateway).first()
    if not gateway_settings or not gateway_settings.is_enabled:
        gateway_title = gateway_settings.title if gateway_settings else 'انتخاب‌شده'
        messages.error(request, f'درگاه «{gateway_title}» در حال حاضر غیرفعال است.')
        return redirect('cart:shopping_payment')
    if not gateway_settings.is_implemented:
        messages.error(request, f'درگاه «{gateway_settings.title}» هنوز فعال نشده است؛ لطفاً درگاه دیگری را انتخاب کنید.')
        return redirect('cart:shopping_payment')
    if not gateway_settings.is_configured:
        messages.error(request, f'اطلاعات اتصال درگاه «{gateway_settings.title}» کامل نشده است.')
        return redirect('cart:shopping_payment')

    customer = _guest_customer(order) if order.user_id is None else _customer_details(request)
    if gateway in MOBILE_REQUIRED_KEYS and not customer['mobile']:
        messages.error(request, 'برای پرداخت اقساطی، شماره موبایل معتبر (مثل 09121234567) را وارد کنید.')
        return redirect('cart:shopping_payment')

    # A double click or a back-and-resubmit must not open a second payment at
    # the provider: send the customer to the payment page opened moments ago.
    recent = (
        PaymentTransaction.objects
        .filter(order=order, gateway=gateway, status='redirected', amount=order.final_price,
                created_at__gte=timezone.now() - PAYMENT_REUSE_WINDOW)
        .order_by('-created_at').first()
    )
    reuse_url = (recent.raw_response or {}).get('redirect_url') if recent is not None else ''
    if reuse_url:
        return _gateway_redirect(request, reuse_url, gateway_settings.title)

    transaction = PaymentTransaction.objects.create(order=order, gateway=gateway, amount=order.final_price)
    try:
        if gateway in GATEWAY_CALLBACK_KEYS:
            callback = request.build_absolute_uri(reverse('payments:gateway_callback', args=[gateway]))
        else:
            callback = request.build_absolute_uri(reverse('payments:callback'))
        authority, url = _start_gateway(GATEWAYS[gateway], transaction, callback, customer)
        transaction.authority, transaction.status = authority, 'redirected'
        transaction.raw_response = {'redirect_url': url}
        transaction.save(update_fields=['authority', 'status', 'raw_response', 'updated_at'])
        return _gateway_redirect(request, url, gateway_settings.title)
    except Exception as exc:
        transaction.status, transaction.raw_response = 'failed', {'error': str(exc)}
        transaction.save(update_fields=['status', 'raw_response', 'updated_at'])
        # The exception text can carry internal hostnames, gateway response
        # fragments or credential-shaped details.  Keep that in the log, and
        # show the customer a message they can quote to support instead.
        logger.exception('خطا در آغاز پرداخت سفارش %s از درگاه %s', order.order_number, gateway)
        messages.error(
            request,
            'اتصال به درگاه پرداخت برقرار نشد. مبلغی از شما کسر نشده است؛ '
            f'لطفاً دوباره تلاش کنید و در صورت تکرار، کد پیگیری «{order.order_number}» را به پشتیبانی اعلام کنید.',
        )
        return redirect('cart:shopping_payment')


def _payment_problem(request, transaction, data, exc):
    """Record a verified payment that cannot be delivered and explain it (refund queue)."""
    # ``_complete`` rolls its transaction back, so the failure must be recorded
    # in a separate statement.  The gateway has already charged the customer:
    # without this row the payment would exist only at the provider and could
    # never be reconciled or refunded.
    duplicate = isinstance(exc, DuplicatePaymentError)
    logger.error(
        'Payment %s for order %s was verified but could not be fulfilled: %s',
        transaction.pk, transaction.order_id, exc, exc_info=True,
    )
    PaymentTransaction.objects.filter(pk=transaction.pk).update(
        status='failed',
        raw_response={**(data or {}), 'error': str(exc), 'unfulfilled': True, 'duplicate': duplicate},
    )
    _notify_unfulfilled(transaction, duplicate=duplicate)
    return render(request, 'payments/payment_unfulfilled.html', {
        'transaction': transaction,
        'duplicate': duplicate,
        'order_url': _order_page_url(transaction.order),
    }, status=409)


@never_cache
def callback(request):
    """بازگشت از زرین‌پال (GET). سفارش مهمان به ورود وابسته نیست؛ تأیید همیشه سمت سرور است."""
    authority = (request.GET.get('Authority') or '').strip()
    if not authority:
        return HttpResponse('شناسه پرداخت نامعتبر است.', status=400)
    transaction = PaymentTransaction.objects.filter(authority=authority).select_related('order').first()
    if transaction is None:
        raise Http404('تراکنش یافت نشد.')
    order = transaction.order
    if order.user_id:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.pk != order.user_id:
            raise Http404('تراکنش یافت نشد.')
    if transaction.status == 'paid':
        # A refreshed, bookmarked or replayed callback URL (even one carrying
        # Status=NOK, or a verify call that now errors) must never downgrade a
        # payment that was already verified and fulfilled to "failed".
        return redirect('payments:successful_done', order_number=order.order_number)
    if request.GET.get('Status') != 'OK':
        transaction.status = 'failed'
        transaction.save(update_fields=['status', 'updated_at'])
        messages.warning(
            request,
            'پرداخت لغو شد و مبلغی از حساب شما کسر نشد. سبد خرید و اطلاعاتی که وارد کرده بودید حفظ شده است؛ '
            'می‌توانید دوباره پرداخت کنید یا روش دیگری را انتخاب کنید.',
        )
        return redirect(_retry_url(order))
    try:
        valid, data = GATEWAYS[transaction.gateway].verify(transaction, request.GET)
    except Exception as exc:
        logger.exception('خطا در تأیید پرداخت %s از درگاه زرین‌پال', transaction.pk)
        valid, data = False, {'error': str(exc)}
    if not valid:
        transaction.status, transaction.raw_response = 'failed', data
        transaction.save(update_fields=['status', 'raw_response', 'updated_at'])
        messages.error(
            request,
            'تأیید پرداخت انجام نشد. اگر مبلغی کسر شده باشد، طبق قوانین بانکی حداکثر تا ۷۲ ساعت به حسابتان '
            f'بازمی‌گردد. می‌توانید دوباره تلاش کنید؛ در صورت نیاز کد پیگیری «{order.order_number}» را به پشتیبانی اعلام کنید.',
        )
        return redirect(_retry_url(order))

    try:
        order = _complete(transaction, data.get('ref_id', ''), data)
    except FulfilmentError as exc:
        return _payment_problem(request, transaction, data, exc)
    _after_payment(request, order)
    return redirect('payments:successful_done', order_number=order.order_number)


@csrf_exempt
@never_cache
def gateway_callback(request, gateway):
    """بازگشت از زرین‌پلاس، اسنپ‌پی و ترب‌پی.

    اسنپ‌پی/ترب‌پی مشتری را با یک POST بین‌سایتی برمی‌گردانند؛ در آن درخواست
    کوکی نشست (SameSite=Lax) فرستاده نمی‌شود، پس این ویو به ورود کاربر وابسته
    نیست و CSRF هم ندارد. تراکنش با شناسهٔ یکتای خود فروشگاه (transactionId) یا
    authority پیدا می‌شود و پرداخت فقط با تأیید سمت سرور از API درگاه نهایی
    می‌شود؛ تکرار بازگشت هم بی‌اثر است.
    """
    if gateway not in GATEWAY_CALLBACK_KEYS:
        return HttpResponse('درگاه نامعتبر است.', status=404)
    data = request.POST if request.method == 'POST' else request.GET
    if gateway == 'zarinplus':
        authority = (data.get('authority') or request.GET.get('authority') or '').strip()
        if not authority:
            if (request.GET.get('status') or '').lower() == 'cancel':
                messages.info(request, 'پرداخت با زرین‌پلاس لغو شد. می‌توانید روش دیگری را انتخاب کنید.')
                return redirect('cart:shopping_payment')
            return HttpResponse('شناسه پرداخت نامعتبر است.', status=400)
        transaction = PaymentTransaction.objects.filter(gateway=gateway, authority=authority).select_related('order').first()
        callback_data = {'authority': authority, 'status': request.GET.get('status', '')}
    else:
        reference = (data.get('transactionId') or '').strip()
        if not reference:
            return HttpResponse('شناسه پرداخت نامعتبر است.', status=400)
        transaction = PaymentTransaction.objects.filter(gateway=gateway, reference_id=reference).select_related('order').first()
        callback_data = {'state': data.get('state', ''), 'transactionId': reference}
    if transaction is None:
        return HttpResponse('تراکنش یافت نشد.', status=404)

    order_number = transaction.order.order_number
    if transaction.status == 'paid':
        return redirect('payments:successful_done', order_number=order_number)
    try:
        valid, details = GATEWAYS[gateway].verify(transaction, callback_data)
    except Exception as exc:
        logger.exception('خطا در تأیید پرداخت %s از درگاه %s', transaction.pk, gateway)
        valid, details = False, {'error': str(exc)}
    if not valid:
        transaction.status, transaction.raw_response = 'failed', details
        transaction.save(update_fields=['status', 'raw_response', 'updated_at'])
        messages.error(
            request,
            'پرداخت انجام نشد یا لغو شد. اگر مبلغی کسر شده باشد، طبق قوانین درگاه بازگردانده می‌شود؛ '
            f'می‌توانید دوباره تلاش کنید و در صورت نیاز کد پیگیری «{order_number}» را به پشتیبانی اعلام کنید.',
        )
        return redirect(_retry_url(transaction.order))

    try:
        order = _complete(transaction, details.get('ref_id', ''), details)
    except FulfilmentError as exc:
        return _payment_problem(request, transaction, details, exc)
    _after_payment(request, order)
    return redirect('payments:successful_done', order_number=order.order_number)


def _notify_unfulfilled(transaction, duplicate=False):
    try:
        from notifications.services import admin_change_url, notify

        if duplicate:
            title = f'پرداخت تکراری برای سفارش {transaction.order.order_number}'
            message = ('مشتری سفارشی را که قبلاً پرداخت شده بود دوباره پرداخت کرده است؛ '
                       'مبلغ این تراکنش را بازگردانید.')
        else:
            title = f'پرداخت موفق سفارش {transaction.order.order_number} قابل تحویل نبود'
            message = 'مبلغ از مشتری کسر شده ولی سفارش تکمیل نشد؛ تراکنش را بررسی و در صورت نیاز مبلغ را بازگردانید.'
        notify(
            'payment_problem', title, message,
            url=admin_change_url(transaction),
            level='danger',
            dedupe_key=f'unfulfilled:{transaction.pk}',
        )
    except Exception:
        logger.exception('ثبت اعلان پرداخت تحویل‌نشده انجام نشد.')


@never_cache
def successful_payment_done(request, order_number):
    """صفحه پایان خرید؛ فایل‌های سفارش پرداخت‌شده آماده دانلود است.

    سفارش اعضا فقط برای صاحبش باز می‌شود (مثل قبل). سفارش مهمان برای نشستی که
    آن را ثبت کرده است؛ اگر درگاه خریدار را در مرورگر دیگری برگرداند، صفحه‌ای
    بدون جزئیات نمایش داده می‌شود که راه دسترسی (لینک ارسالی/پیگیری) را توضیح می‌دهد.
    """
    order = get_object_or_404(Order, order_number=order_number)
    if order.user_id:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.pk != order.user_id:
            raise Http404
        if order.status != 'paid':
            return redirect('dashboard:order_detail', order_number=order.order_number)
        tokens = DownloadToken.objects.filter(order=order, user=request.user).select_related('product', 'order')
        return render(request, 'cart/successful_payment.html', {'order': order, 'tokens': tokens})

    from cart import views_guest

    if not can_access_order(request, order):
        return render(request, 'cart/guest_order_locked.html', {'order_paid': order.status == 'paid'})
    if order.status != 'paid':
        return redirect('cart:guest_order', access_token=order.access_token)
    created = views_guest.create_requested_password_account(request, order)
    if created is not None:
        return created
    tokens = DownloadToken.objects.filter(order=order).select_related('product', 'order')
    context = {
        'order': order,
        'tokens': tokens,
        'is_guest_order': True,
        'order_link': views_guest.order_link(request, order),
    }
    context.update(views_guest.account_card_context(request, order, auto_send=True))
    return render(request, 'cart/successful_payment.html', context)
